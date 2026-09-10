<p align="center">
  <a href="../REPORT_CONTRACT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소스 리포트 계약

[문서 목차](INDEX.ko.md) · [파서 범위](PARSER_SCOPE.ko.md) · [예제](EXAMPLES.ko.md)

공개 alpha 바이너리가 아닌 최신 소스의 스키마 **1.2**를 설명합니다. 리포트 스키마 버전은 아직
0.1.0a1인 패키지 버전과 별개입니다. core, CLI JSON과 로컬 API는 같은 리포트를 직렬화합니다.
이번 리포트 구현은 의존성 분류, AI 제안, 소스 수정이나 대상 코드 실행을 하지 않습니다.

## 호환성과 필드

스키마 1.0은 기존 무버전 목록을 확장했고 1.1은 라우트 직접 선언 `dependencies`를 추가했습니다.
1.2는 상속·직접 선언을 함께 담은 `effective_dependencies`를 추가하며 기존 필드·의미·등록 ID 알고리즘은
유지합니다. 추가 키를 거부하는 소비자는 업그레이드 전에 새 필드를 수용해야 합니다.
버전이 없으면 기존 형식으로 다루고 자동으로 버전이 있는 스키마라고 가정하지
않습니다. 향후 minor 버전에는 필드를 추가할 수 있으며 삭제·이름 변경·
의미 변경에는 major 버전과 문서화한 전환 방법이 필요합니다. 알 수 없는 키는 허용하고 지원하지 않는
major 버전은 거부하는 소비자를 권장합니다.

| 필드                    | 의미                                                                     |
| ----------------------- | ------------------------------------------------------------------------ |
| `schema_version`        | 리포트 계약을 식별하는 문자열, 현재 `1.2`                                |
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
결정론적 소스 탐색/import 합성 순서입니다. 두 의존성 목록은 이 해시에서 제외하므로 스키마 1.2는 다른 등록
근거가 같으면 ID를 바꾸지 않습니다. 진단 문구는 Python/OS 버전에 따라 달라질 수 있습니다.

**ID는 소스 내용 해시, 영구 런타임 식별자나 승인 토큰이 아닙니다.** 선언 위치를 옮기지 않고 함수 본문을
바꿀 수 있습니다. 향후 패치 승인은 정확한 diff와 원본 내용/revision을 별도로 묶고 오래된 승인을 거부하며
사용자 변경을 보존해야 합니다. [작업 흐름 #35](https://github.com/casing1/authzest/issues/35)를 참고하세요.

## 라우트 직접 의존성 근거

스키마 1.1에 모든 route의 `dependencies`를 추가했으며 직접 만든 기존 route의 기본값도 `[]`입니다.
빈 목록은 지원하는 라우트 직접 선언을 수집하지 않았다는 뜻이지 공개 endpoint, 무보호 상태나 의존성
부재를 뜻하지 않습니다. 1.2에서도 이 목록은 라우트 직접 선언만 유지하며 상속 선언은 아래 적용 맥락
목록에만 포함됩니다. 중첩 callable 관계는 아직 수집하지 않습니다.
1.0 리포트에서 이 필드가 없는 것은 생산자가 의존성 근거를 제공하지 않았다는 뜻이며 의존성 스캔의
빈 결과로 해석하지 않습니다.

각 항목은 지원 route에서 확인한 `Depends` 또는 `Security` 호출을 기록합니다.

| 항목                 | 의미                                                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------------------ |
| `kind`               | 이름 철자만이 아니라 지원 import로 식별한 `Depends` 또는 `Security`                                          |
| `target`             | AST로 정규화한 대상 표현식, 기록할 대상이 없으면 null; 평가하지 않음                                         |
| `location`           | 의존성 호출의 원본 위치, 등록 근거와 동일한 경로·UTF-8 좌표 규칙                                             |
| `declaration_level`  | `parameter-default`, `parameter-annotation`, `decorator`                                                     |
| `parameter`          | 매개변수 근거의 매개변수명, decorator 근거는 null                                                            |
| `resolution`         | 허용한 단순/점 연결 이름 구문에 미해석 사유가 없으면 `reference`, 선언의 한계가 하나라도 있으면 `unresolved` |
| `scopes`             | `Security`는 정적으로 확인한 문자열 목록(빈 목록 포함), 미해석 scopes는 null; `Depends`는 항상 null          |
| `unresolved_reasons` | 순서 있는 기계 판독 사유 코드, 리포트 진단에도 기록                                                          |

`reference`는 호출 대상 조회가 아니라 구문 상태입니다. 대상의 존재, import 해석 성공, callable 실행이나
인증·인가 적용을 입증하지 않습니다. `target`은 원본 바이트 그대로가 아닌 정규화된 Python 표현식입니다.
동적 표현식은 신뢰하지 않는 데이터이며 실행할 명령이 아닙니다. 대상/scopes의 한계는 정상 해석한 route를
버리지 않고 남깁니다.

생략한 `Security` scopes와 명시적인 `scopes=None`은 `[]`로 기록합니다. 리터럴 문자열 목록은 원본 순서와
중복을 유지합니다. 동적이거나 잘못된 scopes는 미해석 사유와 null을 기록하며 빈 목록으로 추측하지 않습니다.
scopes는 선언한 문자열이지 검사됐다는 증거가 아닙니다. `use_cache`와 `scope` 인자의 런타임 동작은 해석하지
않습니다. 지원 형식과 진단은 [파서 범위](PARSER_SCOPE.ko.md)를 참고하세요.

## 적용 맥락의 의존성 근거

스키마 1.2는 각 route에 `effective_dependencies`를 추가합니다. 지원하는 app·router·include 상속
선언과 바꾸지 않은 route의 직접 `dependencies`를 합친 목록입니다. 항목은 위와 같은 필드를 사용합니다.
상속 항목의 `declaration_level`은 `application`, `router`, `include`이며 `parameter: null`과 원본
의존성 호출 위치를 유지합니다. `dependencies` 자체는 기존 세 선언 위치 종류만 사용하고 상속 선언을
직접 선언으로 바꾸지 않습니다.

결정론적 순서는 소스 등록 맥락을 나타냅니다. 바깥 owner 생성자 선언, 해당 include 위치 선언,
차례로 안쪽 owner/include 맥락, 마지막으로 라우트 직접 목록입니다. 각 목록의 선언 순서를 유지하며
맥락 전체를 소스 위치순으로 재정렬하거나 중복 제거하지 않습니다. 독립 app/router는 자체 생성자 선언을
포함합니다. 따라서 같은 handler나 URL 경로라도 반복 mount와 app이 다르면 적용 목록이 달라질 수 있습니다.

이는 **런타임 의존성 그래프나 실행 순서 보장이 아닙니다**. callable 하위 의존성, cache 재사용,
override나 인가 적용을 모델링하지 않습니다. 경로만으로 묶지 말고 등록 근거로 각 mount를 해석하세요.
ID에는 여전히 두 의존성 목록을 포함하지 않으며 내용에 묶인 패치 승인이 아닙니다.
합성 한계는 [파서 범위](PARSER_SCOPE.ko.md)를 참고하세요.

직접 선언만 넣어 수동 생성한 기존 route의 적용 목록은 그 직접 선언을 담습니다. 생성자/mount 근거를
만들어내지 않습니다. `effective_dependencies`가 없는 이전 리포트는 이 맥락을 제공하지 않았으며
상속 스캔의 빈 결과로 해석하지 않습니다. 동적 의존성 목록은 항목을 지어내지 않고 확인한 route와 진단을
유지하며 partial 리포트를 만듭니다. `effective_dependencies: []`가 의존성 부재를 입증하지 않습니다.

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
의존성 텍스트는 적용 목록 하나를 출력하며 선언 위치 종류로 상속 항목과 직접 항목을 구분합니다.
종류, 대상, 매개변수, 소스 위치, scopes와 사유를 포함한 reference/unresolved 상태를 표시합니다.
JSON과 로컬 API는 두 의존성 목록을 제공하지만 선택적인
대시보드는 개별 의존성 근거를 아직 표시하지 않습니다.

API는 시작할 때 선택한 workspace에 계속 제한되며 호출자가 다른 경로를 고를 수 없습니다. API에는 strict
옵션이 없으므로 소비자가 `analysis_status`와 `diagnostics`를 확인해야 합니다. 대시보드는 partial/bounded 목록을
구분하고 등록 ID를 행 key로 쓰며 기존 오류는 별도 펼침 목록에 보존합니다.

## 회귀 검증 근거

[모델 계약 테스트](../../tests/test_report_contract.py)는 canonical ID, 루트 이동, 기존 null 근거와 필드/상태
호환성을 검증합니다. [파서 테스트](../../tests/test_report_parser.py)는 소스 위치, 같은 줄 반복 mount, 여러 app,
중첩 cross-file 합성, 알려진 미해석 사례, deferred scope와 소스 전용·한 번 읽기 동작을 검증합니다.
[전달 계층 테스트](../../tests/test_report_transports.py)는 CLI/API 동등성, strict 실패 전 출력과 잘못된 입력·
빈 입력·부분 입력을 검증합니다.

[의존성 모델 테스트](../../tests/test_dependency_contract.py)는 추가 스키마, null/빈 scopes와 등록 ID
유지를 검증합니다. [의존성 파서 테스트](../../tests/test_route_dependencies.py)와
[경계 사례](../../tests/test_dependency_edge_cases.py)는 지원 선언, 별칭, 바인딩 범위와 미해석 형식을
검증합니다. [의존성 전달 계층 테스트](../../tests/test_dependency_transports.py)는 직접 관리하는 예제와
strict 부분 출력을 포함한 core/CLI/API 공통 근거를 검증합니다.

[상속 파서 테스트](../../tests/test_inherited_dependencies.py)는 소스 맥락 합성과 미해석 선언을
검증합니다. [상속 전달 계층 테스트](../../tests/test_inherited_dependency_transports.py)는 반복·다중 app
예제, 공통 리포트와 직접 근거 보존을 검증합니다.
[상속 모델 테스트](../../tests/test_inherited_dependency_contract.py)와
[독립 경계 사례](../../tests/test_inherited_dependency_edge_cases.py)는 호환성, 식별값과 제한된 파일 간 합성을 검증합니다.
