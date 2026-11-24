# 외부 FastAPI 폴더의 수정 제안

[문서](../INDEX.md) · [English](../../../guides/REPOSITORY_PROPOSALS.md) · 한국어

이 미발행 소스 기능은 외부 프로젝트에서 직접 선택한 파일을 읽고 Codex에 새 PoC와 파일 하나의
수정안을 요청할 수 있습니다. 기존 기본 모드는 Python 회귀 테스트 텍스트를 제안하고, 명시적인
`--http-poc` 모드는 제한된 HTTP 요청 데이터를 제안합니다. 어느 모드도 선택한 소스를 내장 시연
소스로 바꾸어 쓰지 않습니다. 외부 프로젝트 지원을 완성하는 동안 정식 발행은 보류합니다.
[확정한 0.1.0 범위](../development/0.1.0-SCOPE.md)를 참고하세요.

현재는 **제안 전용 CLI 단계**입니다. 대상·생성 테스트 실행, 대상 HTTP 접속, 복사본 생성,
패치 적용·복구를 하지 않습니다. 현재 GUI의 활성 흐름은 여전히 내장 owner-read 사례를 사용하며
작업 공간 설정은 정적 스캔 루트만 바꿉니다. 새 저장소 결과 JSON은 아직 GUI의 저장 결과
가져오기에서 지원하지 않습니다.

## HTTP 데이터 제안 선택

제한된 외부 GET 객체 소유권 제안에는 `--http-poc`를 사용합니다. 루트·소스·정책·모델 자리표시자를
검토한 값으로 바꾸고 오프라인 미리보기부터 확인하세요.

```bash
authzest repo-suggest /path/to/project --source app.py --policy policy.md --model EXPLICIT_MODEL --http-poc --preview-only --json
```

이 예시는 입력만 미리 보며 Codex 호출·HTTP 요청·앱 실행을 하지 않습니다. HTTP 모드는 지원하는
GET 선언이 있는 자체 완결형 **ASCII 식별자 이름의 단일 `.py` 소스 파일**만 허용하며 package·중첩
Python 경로·`__init__.py`는 지원하지 않습니다. 소스는 **16 KiB**, 정책은 **8 KiB**로 제한하고 이 모드의
`--context`는 거부합니다. `--app-attribute`는 선택 사항이고 기본값은 `app`이며 `--http-poc`에서만
사용할 수 있습니다. 일반 식별자 형식의 앱 속성·모듈, import root `.`, lifespan off와 인증 override
없음은 요청에 묶인 선언이지 import 가능한 앱이나 대표적인 사용자 설정이 존재한다는 증거가 아닙니다.

새 요청은 캡처한 입력에서 직접 만드는 스키마 **2.0**, 종류 `repository-http-proposal-request`이며
저장한 v1.0/v1.1 요청을 변환하지 않습니다. 전체 소스·정책·선택 인터페이스·부분 정적 근거·모델·
지시문·프롬프트·출력 스키마가 요청 식별자에 결합합니다. 공유 미리보기 wrapper는 스키마 2.0의
`repository-http-sharing-preview`입니다. 독립 사례의 예상 정답은 모델에 제공하지 않으며 정책은
검증하지 않은 사용자 제공 의도로 유지합니다.

`proposed-change` 응답에는 새로 작성한 대체 소스(`after_text`)와 `method`, `path`, `headers`로
구성된 PoC 데이터 하나가 있습니다. 메서드는 `GET`이며 경로는 query string·상위 경로 이동·절대 URL이
없는 제한된 리터럴 상대 경로입니다. `headers`는 중복되지 않는 `{name, value}` 레코드 0~3개의 배열로,
이름은 `x-user`, `x-user-id`, `x-role`만 허용하고 값은 제한된 합성 `test-*` 문법을 사용합니다.
예상 응답·assertion·Python/pytest·명령·인증정보는 PoC 필드가 아닙니다. 합성 사용자와 익명 정책
검사는 실제 인증 체계의 안전성을 입증하지 않습니다.

실제 제안을 요청하려면 `--http-poc`는 유지하고 `--preview-only`를 제거합니다. 아래의 현재 공유
확인·재캡처 보호를 그대로 사용하며 새 정확한 공유 결정 뒤 adapter를 최대 한 번 호출합니다.
애플리케이션 재시도·모델 대체는 없습니다. 최종 결과 종류는 스키마 2.0의
`repository-http-suggestion`이며 응답 종류는 `repository-http-proposal`입니다. 호스트는 소스 하나의
diff를 계산하고 전체 응답을 결합하며 PoC 데이터를 해시합니다. 생성 테스트 경로나 꾸며낸 T/pytest
결과는 없습니다. 실행·복사본 생성·패치/원본 적용·복구는 모두 미실행이며 인가 상태는 unknown,
`verified_fix`는 false입니다. 변경 없음·unknown·거절도 정상 제안 결과입니다.

새 요청과 이름이 분리된 `suggest_repository_http` adapter 진입점은 오프라인·모의 프로토콜로
검사했으며 고정한 Codex 0.153.0과 스키마 2.0의 실제 제공자 수용 실행은 아닙니다. 후속 격리 A/B 실행,
독립 사례·원본 수정·GUI 가져오기는 별도 연결이 필요합니다. 이 모드의 저장 결과 GUI는 릴리스
목표이며 현재 구현된 importer가 아닙니다.

## 선택할 입력 준비

POSIX에서 갱신한 non-frozen 소스 설치와 활성화한 Python 환경을 사용하세요. 이 제안 전용 CLI에는
대시보드·프런트엔드 빌드나 Docker 런타임이 필요하지 않습니다. 기존 Codex adapter에는 신뢰한
Codex CLI **0.153.0**, 기존 ChatGPT 로그인과 접근 가능한 명시적 모델 ID가 필요합니다.
오프라인 미리보기는 Codex에 접속하거나 계정을 사용하지 않습니다.

외부 프로젝트 루트에 상대적인 경로를 선택합니다.

| 입력 | 요구 사항                                                                                    |
| ---- | -------------------------------------------------------------------------------------------- |
| 소스 | `--source`로 선택하는 수정 대상 Python 파일 하나                                             |
| 정책 | `--policy`로 선택하는 내용이 있는 UTF-8 `.md` 또는 `.txt` 문서 하나, 의도한 접근 규칙 설명   |
| 문맥 | 기본 모드만: `--context`로 다른 Python 파일 최대 4개 선택, 읽기 전용이며 추가 수정 대상 아님 |

정책은 사용자가 제공한 의도이며 추론했거나 검증한 런타임 정답이 아닙니다. 누가 어떤 자원에
접근할 수 있는지, 의도한 거절·공개 동작, 테스트 준비나 누락된 fixture 가정을 설명하세요.
기본 모드에서는 인증·소유권 도우미가 다른 파일에 있다면 필요한 파일을 문맥으로 선택합니다.
HTTP 모드는 자체 완결 소스 한 파일로 제한하며 문맥 파일을 거부합니다.
의존성·관계없는 파일을 자동 탐색·읽기·import하지 않습니다.

경로는 명시적 POSIX 상대 경로여야 하며 절대 경로, 숨김 구성요소, 빈 구성요소·현재/상위 디렉터리
표기, 역슬래시·제어 문자를 허용하지 않습니다. 심볼릭 링크·하드링크·디렉터리와 FIFO 같은 특수
파일은 거부합니다. 루트와 상위 디렉터리도 심볼릭 링크 없이 도달해야 합니다. macOS의 `/tmp`
별칭 대신 `/private/tmp`처럼 실제 경로를 사용하세요.

Python 파일마다 **16 KiB**, 정책은 **8 KiB**, 선택한 전체 바이트는 **64 KiB**로 제한합니다.
입력은 NUL 없는 UTF-8이어야 하며 빈 Python 문맥 파일은 허용합니다. loader는 descriptor를
유지하고 바이트·이름·메타데이터를 재확인해 일반 편집·교체를 탐지합니다. 적대적 동시 writer에
대한 원자적 스냅샷을 보장하지는 않습니다.

선택 소스 파싱은 **파일마다 등록 추가 64개·진단 64개**에서도 중단합니다. 등록 작업에는 최종
표시 라우트뿐 아니라 중간 router 복제가 포함됩니다. 합친 라우트·진단 근거도 각각 64개로 제한합니다.
따라서 최종 목록이 작더라도 복잡한 조합은 거부될 수 있으며, 이 제안 경로는 무제한 router 그래프를
확장하지 않습니다.

## 공유 전 미리보기

루트·선택 경로와 `EXPLICIT_MODEL`을 검토한 값으로 바꾸세요. 다음 예시는 소스와 정책만 선택합니다.

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --model EXPLICIT_MODEL --preview-only
```

필요한 문맥만 명시적으로 추가합니다. 파일을 더 선택하려면 문맥 옵션을 반복합니다.

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --context auth.py --model EXPLICIT_MODEL --preview-only --json
```

미리보기에는 선택한 소스·문맥·정책 전체, 소스 해시, 정적 선언·진단·한계, 프롬프트·응답 스키마와
요청 제한을 표시합니다. 파서는 캡처한 Python 바이트를 사용하며 대상을 다시 열거나 import하지
않습니다. 선택 파일 근거는 앱 전체 import·의존성 그래프를 해석하거나 런타임 접근통제를 증명하지
않습니다. 문맥이 부족하면 unknown·거절이 타당한 결과일 수 있습니다.

로컬 절대 루트는 제공자 요청에 포함하지 않습니다. 선택한 텍스트 자체에는 경로·비밀정보가 있을 수
있습니다. 명시적 선택은 비밀정보 탐지가 아니므로 전송할 요청 전체를 검토하세요.

## 제안 요청

미리보기 플래그를 빼면 대화형 공유 단계로 들어갑니다.

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --context auth.py --model EXPLICIT_MODEL
```

현재 미리보기 전체를 검토한 뒤 표시된 공유 확인 문구를 정확히 입력하세요. Enter는 거절,
cancel은 취소입니다. 결정은 **300초** 후 만료되며 현재 호출에 묶입니다. 전송 전 모든 선택 파일을
다시 캡처하고 변경되었거나 사용할 수 없으면 요청을 중단합니다. 이전 문구·저장 JSON·편집한 요청은
새 호출을 승인하지 않습니다.

로컬 adapter 호출은 최대 한 번이며 adapter 제한은 최대 **120초**, 정리 대기는 별도입니다.
애플리케이션 재시도·모델 대체는 없습니다. Codex 내부 통신 재시도와 실제 토큰·비용은 별도 상한을
보장하지 못하며 기존 계정 사용량이 소비될 수 있습니다. 기존 ChatGPT 로그인을 사용하고 Codex의
harness 문맥이 추가됩니다. 신뢰한 transport는 기존 빈 작업 디렉터리·도구 제한 제어를 사용하며
대상 프로젝트를 에이전트 작업 공간으로 열지 않습니다.

## 결과 읽기·보관

`--http-poc`가 없으면 최종 종류는 기존 `repository-suggestion`입니다. 제안 상태는 `proposed-change`, `no-change`, `unknown`,
`refused`이며 통신·입력·만료 실패는 별도의 워크플로 상태로 유지합니다. 변경 제안에는 선택한 소스의
완전한 대체 코드와 새 pytest 회귀 테스트가 들어 있습니다. 호스트는 응답을 요청·변경 전 해시에
묶고 제한된 Python AST 형태를 검사한 뒤 정확한 diff를 계산합니다. 이 검사는 안전한 실행·정책
정확성·공격 재현·테스트 수집·수정 검증을 입증하지 않습니다.

제안 테스트 경로는 `tests/test_authzest_regression.py`입니다. 출력상의 경로 이름일 뿐이며 이 단계는
그 경로를 읽거나 없음을 검사하거나 생성·덮어쓰지 않습니다. 문맥 파일은 수정 대상이 아닙니다.
두 코드와 호스트가 계산한 diff뿐 아니라 근거·가정·불확실성·한계도 확인하세요.
실행·적용·복구는 미실행으로 남습니다.

stdout에 최종 JSON 하나를 받으려면 JSON 옵션을 사용하고 검토한 비공개 위치에 저장하세요.
공유 미리보기 전체와 입력 요청은 stderr로 보내므로 결정 전에 검토해야 합니다.

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --context auth.py --model EXPLICIT_MODEL --json
```

JSON에는 선택한 소스·정책과 생성 코드가 들어 있으므로 비공개 소스 자료로 취급하세요. 현재 GUI에
가져와 owner-read 적용·검사·복구 흐름으로 이어질 것으로 기대하지 마세요. 외부 비공개 복사본 준비,
승인한 적용, 격리한 before/after 실행·복구와 GUI 연동은 후속 작업입니다.
[외부 파일 흐름 설계](../development/REPOSITORY_FILE_WORKFLOW.md)가 다음 단계를 정의합니다.
S1 Python API는 메타데이터만 준비하며 해당 동작이나 원본 프로젝트의 최종 쓰기를 활성화하지 않습니다.
별도의 [S2 Python 파일 세션 API](../reference/REPOSITORY_FILE_SESSION.md)는 비공개 파일 전환을 구현하고
오프라인으로 검사합니다. 이 명령은 해당 API를 호출하지 않으며 외부 런타임·조작 흐름·GUI 연결은 미완료입니다.
[S3 v1.1 인터페이스·사례 비교 계약](../reference/REPOSITORY_VERIFICATION.md)도 별도 순수 API입니다.
명령의 기본 모드는 v1.0을 유지하고 명시적 HTTP 모드는 v1.1 테스트 인터페이스가 아닌 별도 2.0
요청을 사용합니다. 제공된 비교 자료로 쓰기를 켜거나 실제 실행을 입증할 수 없습니다.
[런타임 기반](../reference/REPOSITORY_RUNTIME.md)은 별도 내부 checkpoint·봉인 입력과 모의 검사한
guest/HTTP 소스를 추가합니다. 정적 생성 계획과 미빌드 recipe로 이 명령의 실행·파일 흐름을
활성화하지 않습니다.

## 검증 경계

이번 구현은 직접 관리하는 임시 입력, 오프라인·mock adapter와 신뢰한 가짜 프로토콜 peer로
검사합니다. 해당 테스트가 실제 제공자 호출이나 사용자 비공개 저장소 공유를 입증하지는 않습니다.
내장 owner-read 관찰과 이전 릴리스 후보 검사는 각각 기록된 소스·범위에 해당하며 외부 프로젝트
종단간 수용 결과가 아닙니다.

[공식 App Server turn 문서](https://learn.chatgpt.com/docs/app-server#turns)는 turn별 `outputSchema`를
설명합니다. 고정한 로컬 Codex 버전의 실제 스키마 2.0 호환성이나 이번 전달에서 모델 생성이
성공했다는 근거는 아닙니다.
