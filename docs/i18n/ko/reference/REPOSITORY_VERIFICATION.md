# 외부 테스트 인터페이스와 제공 데이터 비교 (S3)

[문서](../INDEX.md) · [English](../../../reference/REPOSITORY_VERIFICATION.md) · 한국어

[#206](https://github.com/casing1/authzest/issues/206)은
[외부 파일 흐름 설계](../development/REPOSITORY_FILE_WORKFLOW.md)를 위한 순수 Python 계약을
추가합니다. 모델을 시작하거나, 소스·테스트를 import/수집/실행하거나, guest를 실행하거나, 파일을
읽거나, 쓰기를 승인하지 않습니다. 현재 `repo-suggest`, adapter와
[S2 파일 세션](REPOSITORY_FILE_SESSION.md)은 기존 v1.0 경계를 유지합니다. 새 요청 타입은 해당
API나 현재 GUI에서 받지 않습니다.

## 모델에 명시적으로 제공하는 테스트 인터페이스

`build_repository_test_request(base, entry_source=..., import_root='.', app_attribute='app')`은
별도 동결된 `RepositoryTestRequest`를 만들며 스키마 `1.1`을 사용합니다. 기반은 검증한 현재
`RepositoryProposalRequest`(`1.0`)이며 기존 payload·prompt·식별자는 바뀌지 않습니다. 새 config는
prompt 버전 `external-repository-test-proposal-v1.1`을 정확하게 나타냅니다.
`validate_repository_test_request`는 선택 내용 전체, 정적 근거, 인터페이스, prompt, schema와
식별자를 재구성합니다. 응답 검증과 호스트 계산 미리보기는 새 버전·ID를 사용하면서 기존의 제한된
비활성 소스·테스트 규칙을 유지합니다.

선언한 `test_interface`는 다음을 결합합니다.

- 이미 선택한 Python `entry_source`, import root `.` 또는 `src`, 도출한 module과 일반 ASCII
  Python 앱 속성 식별자. 기본값은 `app`입니다.
- 신뢰하는 `client` fixture, lifespan `off`, 인증 override `none`.
- 인터페이스 schema `1.0`과 자체 canonical 식별자. 새 prompt·요청 식별자에도 포함합니다.

Module 구성 요소는 ASCII 식별자여야 하며 keyword가 될 수 없습니다. 선택한 package 초기화 파일이
필요합니다. 자동 탐색, factory 호출, 합성 `__init__.py`, 프로젝트 의존성 설치, conftest/plugin 또는
setup callback은 선언하지 않습니다. `src`를 쓰면 선택한 Python 파일이 모두 그 root 아래에 있어야
합니다. `pkg.py`와 `pkg/__init__.py`를 함께 두는 경우처럼 물리적 별칭과 논리적 파일/package 또는
module/submodule 충돌을 거부합니다. 유효한 선언만으로 앱 객체, 사용 가능한 import, 설치된 의존성,
작동하는 fixture를 확인할 수는 없습니다. 이는 이후 런타임 전까지 미확인 상태입니다.

모델은 선택한 소스·정책·근거와 명시적 인터페이스를 받습니다. 독립 사례 집합, case ID, 기대값이나
사람의 검토 선언은 받지 **않습니다**. 제공자 접근, 공유 결정과 transport 호환성은 별도 조건입니다.
[공식 App Server 문서](https://learn.chatgpt.com/docs/app-server#turns)는 turn별 `outputSchema`를
설명하지만 그 문서가 이 프로젝트의 고정된 `0.153.0` adapter와 새 요청의 호환성을 입증하지는
않습니다. 이번 단계에는 RPC/pin 변경이나 실제 모델 호출이 없습니다.

## 호스트에만 두는 독립 사례 선언

`build_repository_cases(data)`는 동결된 `RepositoryCaseSet`을 반환하고,
`validate_repository_cases`는 이를 정확히 재구성합니다. 기반 정보는 선택한 소스, 정책, 전체 선택
내용과 테스트 인터페이스를 식별해야 합니다. 작성자·가정·적용 가능성·이유는 **제공된 데이터**이며
인증된 검토, 정책의 참값 또는 구체적인 정답 수용이 아닙니다.

닫힌 schema는 고유 사례 4–8개, 지정된 회귀 사례 정확히 하나와 비어 있지 않은 이유를 요구합니다.
그 사례가 선언한 before 응답은 원하는 after 응답과 달라야 합니다. Coverage 이름은 owner,
non-owner, anonymous, normal-use, public입니다. 각각 존재하는 사례를 참조하거나 적용하지 않는
이유를 제시해야 하며 normal-use는 항상 대조 사례를 참조해야 합니다. AST나 누락된 dependency에서
공개 의도를 추론하지 않고도 명시적 public coverage를 지원합니다. 이는 계약 테스트용 선언이며 동결된
독립 benchmark나 관리자가 새로 승인한 정책 정답은 아닙니다.

각 사례에는 literal GET 경로 하나와 별도의 정확한 before/after 응답 값이 있습니다. 제한과 초기
미지원 형식을 명시합니다.

- 사례 문서: 최대 64 KiB. 제공된 phase frame: 최대 64 KiB.
- 경로: 최대 512 ASCII 문자, 선행 slash 하나, literal 문자·숫자와 `/_.-`.
  `//`, dot segment, query, fragment, percent encoding, backslash와 절대 URL은 거부합니다.
- Header: 소문자 `x-user`, `x-user-id`, `x-role`만 허용합니다. 값은 최대 세 개이며 각각 최대
  64 ASCII 문자와 `test-` 합성 token 접두사를 사용합니다. Host, Authorization, Cookie,
  proxy/framing header, 실제 자격정보, request body, script, callback과 redirect는 지원하지
  않습니다. 접두사는 이름에 대한 선언일 뿐 비밀 탐지나 합성 신원에 대한 증거가 아닙니다.
- 기대 status: 2xx 또는 4xx. Body: 타입을 유지하는 JSON 또는 명시적 empty이며 204/205는 빈
  body를 요구합니다. JSON은 최대 4 KiB, 깊이 8, 값 node 128개, 문자열 값 1,024 UTF-8 byte,
  key 128 byte입니다. 정수는 ±(2^53−1) 범위이며 실수는 유한해야 합니다. Boolean·정수·실수
  타입은 서로 구분하고 객체 key 순서는 무시합니다. 중복 JSON key와 알 수 없는 필드는 거부합니다.

## 결합과 관찰자용 투영

`build_repository_verification_plan(request, response, cases)`는 현재 `1.1` 입력을 검증하고
요청·응답 전체 식별자, 선택한 before와 제안한 after의 hash, 생성 테스트 hash, 인터페이스와
호스트 전용 사례를 결합합니다. 유효한 변경 없음 상태에는 계획을 반환하지 않습니다. 사례 기반 정보는
현재 입력과 정확히 일치해야 합니다. `validate_repository_verification_plan`은 모든 현재 입력에 대해
계획 전체를 재구성합니다. 편집한 메타데이터의 hash를 다시 계산해도 일치하게 만들 수 없습니다.

`prepare_repository_observer_schedule(..., phase=...)`는 plan ID, phase와 GET 요청 기록만
투영합니다. 기대 정답, 소스·테스트 텍스트, 정책, 회귀 이유나 작성자는 포함하지 않습니다. 계획은
비공개 호스트 데이터로 유지합니다. 데이터 흐름은 다음과 같습니다.

```text
v1.0 base request → opt-in v1.1 test-interface request (model view)
current request + proposal + independent cases → verification plan (host only)
plan + phase → request-only observer schedule
supplied frame + current plan/inputs → candidate and comparison (unverified)
```

Hash는 선언을 결합합니다. 실제 staging 파일을 측정하거나, 관찰자를 인증하거나, 명시한 소스·테스트가
실행됐음을 입증하지 않습니다. v1.1 downgrade, 가져온 결과나 비교로 S2 쓰기를 활성화할 수 없습니다.

## 제공된 frame과 정직한 비교

`decode_repository_phase_candidate`는 현재 계획과 before/after phase에 대해 크기가 제한된
`repository-supplied-phase` frame을 검사합니다. 되돌려 받은 소스·테스트·인터페이스 결합 정보가
일치해야 합니다. 계획한 모든 사례는 schedule 순서대로 정확히 한 번씩 나타나며 타입을 유지한 응답
또는 닫힌 오류 코드 하나를 가져야 합니다. 타입 있는 관찰은 3xx/5xx를 기록할 수 있지만 비교에서는
오류로 처리합니다. 304도 빈 body를 요구합니다. 이 codec은 raw HTTP/TCP header, fragment나 framing을
parse하지 않습니다. 이후 transport와 관찰자 코드가 이러한 별도 속성을 확인해야 합니다.

Pytest 데이터에는 크기가 제한된 정확한 정수 count, exit code와 제공된 `failure_kind`인
`assertion`, `other`, `none`이 들어 있습니다. Cleanup에는 정확히 T/A/B 상태만 있습니다.
Before 후보의 조건은 다음과 같습니다.

- 모든 응답이 선언한 before 값과 일치하며 지정된 사례는 원하는 after 동작과 다른 값을 가집니다.
- 수집된 테스트가 0개가 아니고 제공된 assertion 실패가 정확히 하나이며 나머지는 모두 통과하고,
  exit 1이고 error/skip/xfail/xpass가 없으며 세 guest 모두의 cleanup이 제공 데이터상 확인됨입니다.

After 후보의 조건은 선언한 모든 after 대조 사례, 0개가 아닌 전체 통과 pytest count, exit 0,
failure kind `none`, error/skip/xfail/xpass 없음, 제공 데이터상 전체 cleanup 확인됨입니다.
일반 예외, 누락·잘못된 관찰, setup/transport 오류, timeout, server error나 미확인 cleanup은 이 조건을
충족할 수 없습니다. Pytest는 값이 일관되더라도 신뢰하지 않는 보조 데이터입니다.

`compare_repository_phase`는 잘못된 frame 데이터를 처리하기 **전에** 현재 계획·입력을 검증합니다.
유효한 frame은 각 match/mismatch/error를 보존합니다. 잘못된 frame은 모든 계획 사례를 invalid로
보존하고 닫힌 진단 코드를 사용하며 원본 오류를 되돌려 주지 않습니다. 확보한 일부만 채점하지 않습니다.
`validate_repository_phase_candidate`는 제공된 후보를 재구성하고 권한을 높인 flag를 거부합니다.

완전히 일치한 결과도 항상 `evidence_basis: supplied-unverified`, execution `not-run`,
authorization `unknown`, `verified_fix: false`, `live_evidence: false`, `writes_authorized: false`를
유지합니다. `supplied_criteria_met`는 제공된 선언의 비교 조건 충족 여부일 뿐입니다. 호출자는 일치하는
응답·pytest label·cleanup을 꾸며낼 수 있으며 이것으로 결함을 재현하거나 수정 효과를 검증한 것이
되지는 않습니다.

## 남은 제품 작업

별도 [런타임 기반](REPOSITORY_RUNTIME.md)은 봉인한 선택 바이트 staging, T/A/B 진입점 소스, 제한된
raw HTTP 캡처와 정적 생성 계획을 구현하고 비활성 파일·가짜 peer로 검사합니다. 이미지 빌드·수용과
직접 반환하는 실제 외부 phase 결과는 미완료입니다. 이후 CLI 조작 흐름을 그 live 결과와
S2 결정에 결합하고 제한된 설치형 외부 흐름을 검증하고 별도로 검토한 원본 프로젝트 최종 수정을
구현하고 공통 GUI 엔진에 연결합니다. #152/#150은 계속 열어 둡니다. 이 순수 계약이 계정 사용,
실제 외부 프로젝트 실행, 위험 수용, tag나 릴리스를 승인하거나 입증하지는 않습니다.
