<p align="center">
  <a href="../REPORT_CONTRACT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소스 리포트 계약

[문서 목차](INDEX.ko.md) · [파서 범위](PARSER_SCOPE.ko.md) · [예제](EXAMPLES.ko.md)

공개 alpha 바이너리가 아닌 최신 소스의 스키마 **1.0**을 설명합니다. 리포트 스키마 버전은 아직
0.1.0a1인 패키지 버전과 별개입니다. core, CLI JSON과 로컬 API는 같은 리포트를 직렬화합니다.
이번 리포트 구현은 의존성 분류, AI 제안, 소스 수정이나 대상 코드 실행을 하지 않습니다.

## 호환성과 필드

첫 버전 스키마는 기존 무버전 목록에 필드를 추가합니다. 기존 필드와 의미는 유지하지만 추가 키를
거부하는 소비자는 업그레이드 전에 새 필드를 수용해야 합니다. 버전이 없으면 기존 형식으로 다루고
자동으로 1.0이라고 가정하지 않습니다. 향후 minor 버전에는 필드를 추가할 수 있으며 삭제·이름 변경·
의미 변경에는 major 버전과 문서화한 전환 방법이 필요합니다. 알 수 없는 키는 허용하고 지원하지 않는
major 버전은 거부하는 소비자를 권장합니다.

| 필드                    | 의미                                                                     |
| ----------------------- | ------------------------------------------------------------------------ |
| `schema_version`        | 리포트 계약을 식별하는 문자열, 현재 `1.0`                                |
| `root`                  | 선택한 스캔 루트의 절대 경로, 로컬 환경 맥락이며 등록 ID에는 제외        |
| `python_files`          | 파싱하지 못한 파일을 포함한 선택된 Python 파일 수                        |
| `route_count`, `routes` | 발견한 소스 등록/선언의 수와 순서 있는 목록                              |
| `parse_errors`          | 기존 오류 문자열 보존, 절대 경로와 플랫폼별 문구를 포함할 수 있음        |
| `codex_status`          | 현재 scan은 `disabled`이며 AI 호출 없음                                  |
| `analysis_status`       | 진단 또는 기존 parse error가 하나라도 있으면 `partial`, 아니면 `bounded` |
| `diagnostics`           | 구조화된 소스·읽기·미지원 패턴 진단의 순서 있는 목록                     |

어느 상태도 런타임 전체 범위, 취약점 검출이나 접근통제 안전성을 보장하지 않습니다. `bounded`는
지원 범위에서 진단을 수집하지 않았다는 뜻이며 모든 미지원 구문을 인식했다는 뜻이 아닙니다.
빈 소스 디렉터리도 bounded·라우트 0개를 반환할 수 있습니다. 일부 미해석 import, receiver 별칭,
middleware와 동적 코드는 진단 없이 생략될 수 있으므로 파서 범위를 확인하세요.

## 등록 근거

각 route는 기존 `path`, `methods`, `function`, `file`, `line`을 유지합니다. 기존 줄 번호는 함수 정의를
가리키며 데코레이터나 mount 줄이 아닙니다. 다음 두 필드를 추가합니다.

- `registration_id`: `route-`와 SHA-256 16진수 digest로 구성한 불투명 식별자.
- `registration`: 원본 선언·owner, 확인한 app 맥락, include chain과 scope.

파서가 출력하는 route에는 두 필드를 채웁니다. 근거 없이 직접 만든 기존 core `Route`는 두 필드를
null로 직렬화하며 소비자가 확인된 소유 관계를 임의로 만들어내면 안 됩니다.

| 등록 근거 항목    | 의미                                                                                               |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| `declaration`     | `@` 다음 데코레이터 호출 표현식의 소스 위치                                                        |
| `owner`           | 원본 route owner의 `kind`와 생성자 `location`                                                      |
| `application`     | 합성한 route를 받는 소스 FastAPI owner, 독립 router는 null                                         |
| `include_chain`   | 바깥→안쪽 등록 순서, 각 항목은 호출 `location`, `parent`, `router`, 호출에 직접 쓴 리터럴 `prefix` |
| `execution_scope` | `module` 또는 `deferred`, 함수 본문 목록화는 호출됐다는 증거가 아님                                |

위치는 `file`, `line`, `column`을 갖습니다. 루트 안의 새 근거·진단 파일 경로는 상대 POSIX 구분자를
사용합니다. 기존 route `file`은 호환성을 위해 OS 기본 구분자를 유지합니다. 줄과 열은 1부터 시작하며
열은 편집기 표시 칸이나 Unicode 문자 수가 아닌 UTF-8 바이트 수입니다. 알 수 없는 오류 좌표는 null입니다.
owner 위치는 변수 대입 대상이 아닌 생성자 호출을 식별합니다.

같은 경로의 반복 등록도 정확한 decorator·owner/app·include 위치로 구분하며 같은 줄의 별도 호출도
구분합니다. 중첩 chain은 지원하는 각 소스 등록을 기록하지만 실제로 소스를 import했거나 endpoint를
배포했다는 뜻은 아닙니다.

digest는 route 경로·메서드·함수·POSIX 상대 파일·함수 줄과 전체 registration 객체를 담은 canonical JSON으로
만듭니다. JSON 키를 정렬하고 구분자를 압축하며 Unicode를 유지한 UTF-8 바이트를 해시합니다. 같은 입력은
반복 스캔이나 선택 루트 이동 후에도 같은 ID를 만듭니다. route 순서는 endpoint 알파벳순이 아니라
결정론적 소스 탐색/import 합성 순서입니다. 진단 문구는 Python/OS 버전에 따라 달라질 수 있습니다.

**ID는 소스 내용 해시, 영구 런타임 식별자나 승인 토큰이 아닙니다.** 선언 위치를 옮기지 않고 함수 본문을
바꿀 수 있습니다. 향후 패치 승인은 정확한 diff와 원본 내용/revision을 별도로 묶고 오래된 승인을 거부하며
사용자 변경을 보존해야 합니다. [작업 흐름 #35](https://github.com/casing1/authzest/issues/35)를 참고하세요.

## 진단

진단은 `code`, `message`, `severity`, `location`을 담습니다. severity는 소스 처리의 `error` 또는 `warning`이며
취약점 심각도가 아닙니다. 파일 읽기·파싱·디코딩 실패는 error, 확인한 미지원 선언은 warning입니다. 어느 쪽도
분석을 partial로 만듭니다. 기존 parse error는 구조화된 대응 진단과 함께 보존하므로 두 목록을 독립 실패로
더하지 않습니다.

지원하는 사유 코드와 발생 범위는 [파서 범위](PARSER_SCOPE.ko.md)에 있습니다. 특히 미해석 include 자식은
근거가 있는 include 시도 위치에서 진단하며, 모든 미해석 import를 목록화하는 것은 아닙니다. 소스 파싱에
실패해도 다른 파일의 유효한 route는 유지합니다. JSON 진단은 구조화된 출력이지 HTML에 안전한 문자열이나
실행할 명령이 아닙니다.

## CLI와 API 동작

설치 후 소스 checkout에서 실행합니다.

```bash
authzest scan examples/fastapi_inventory
authzest scan examples/fastapi_inventory --json
authzest scan examples/fastapi_inventory --json --strict
```

| 상황                             | 기본 CLI            | `--strict` CLI      | 로컬 scan API                        |
| -------------------------------- | ------------------- | ------------------- | ------------------------------------ |
| 유효한 루트, bounded 목록        | 종료 0, 리포트      | 종료 0, 리포트      | HTTP 200, 리포트                     |
| 유효한 루트, 확인한 partial 목록 | 종료 0, 리포트      | 종료 1, 리포트      | HTTP 200, 리포트                     |
| 루트가 없거나 디렉터리 대신 파일 | 종료 2, stderr 오류 | 종료 2, stderr 오류 | 설정한 workspace가 사라지면 HTTP 400 |

기존 스크립트의 기본 종료 동작을 유지하기 위해 strict는 opt-in입니다. 보안 finding이 아닌 확인한 분석
한계에 실패합니다. JSON 모드는 strict가 종료 1을 반환하기 전에 전체 리포트를 stdout에 출력하고 stderr에
진단 텍스트를 섞지 않습니다. 사람이 읽는 출력에는 소스 경로, 등록 ID, app/include 위치, scope와 진단 상세가
있습니다. 텍스트 배치는 사람용이며 연동에는 버전이 있는 JSON을 사용하세요. 예상 밖 내부 예외는 보안 판정이
아닙니다.

API는 시작할 때 선택한 workspace에 계속 제한되며 호출자가 다른 경로를 고를 수 없습니다. API에는 strict
옵션이 없으므로 소비자가 `analysis_status`와 `diagnostics`를 확인해야 합니다. 대시보드는 partial/bounded 목록을
구분하고 등록 ID를 행 key로 쓰며 기존 오류는 별도 펼침 목록에 보존합니다.

## 회귀 검증 근거

[모델 계약 테스트](../../tests/test_report_contract.py)는 canonical ID, 루트 이동, 기존 null 근거와 필드/상태
호환성을 검증합니다. [파서 테스트](../../tests/test_report_parser.py)는 소스 위치, 같은 줄 반복 mount, 여러 app,
중첩 cross-file 합성, 알려진 미해석 사례, deferred scope와 소스 전용·한 번 읽기 동작을 검증합니다.
[전달 계층 테스트](../../tests/test_report_transports.py)는 CLI/API 동등성, strict 실패 전 출력과 잘못된 입력·
빈 입력·부분 입력을 검증합니다.
