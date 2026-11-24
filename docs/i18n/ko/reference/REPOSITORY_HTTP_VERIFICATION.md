<p align="center">
  <a href="../../../reference/REPOSITORY_HTTP_VERIFICATION.md">English</a> ·
  <strong>한국어</strong>
</p>

# HTTP 정책 사례와 A/B 검사 준비

[문서 목차](../INDEX.md) · [확정 범위](../development/0.1.0-SCOPE.md) ·
[제안 CLI](../guides/REPOSITORY_PROPOSALS.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## 현재 제공 범위

이 소스 API는 제공된 자료·직접 관리하는 비활성 파일·가짜 협력자로 외부 단일 파일 HTTP 흐름을
준비합니다. 이미지 빌드·Engine/소켓 접속·앱 실행·파일 작업 권한을 제공하지 않습니다. CLI의
`--http-poc`는 계속 제안 전용이며 결과 GUI 가져오기도 미지원입니다. 기존 v1.0/v1.1·T/A/B와
내장 시연 인터페이스는 고유한 식별자와 동작을 유지합니다.

새 모드는 별도 schema 2.0 사례·계획·schedule·제공 phase·manifest·runtime-profile 종류와
`repository-http-*` 식별자를 사용합니다. 역할은 A/B뿐이며 생성 테스트 파일·pytest 결과·꾸며낸
T 식별자를 요구하지 않습니다. 숫자 버전이 같다는 이유로 호환되는 것은 아닙니다.

## 독립 사례와 정확한 PoC 대조

`authzest.runner.repository_http_cases`는 `RepositoryHttpCaseSet`,
`build_repository_http_cases(data)`, `validate_repository_http_cases(cases)`를 제공합니다.
문서는 선택 소스·정책의 해시와 선택 식별자를 명시적인 HTTP 인터페이스에 결합하며 다음을 담습니다.

- 순서와 고유 ID가 있는 사례 4~8개. 각각 GET 한 번과 정확한 타입의 before/after 상태·JSON 또는
  빈 body 기대값을 정의합니다.
- before와 after 기대값이 다른 지정 회귀 사례 하나와 그 이유.
- 작성 주체·가정, 소유자·비소유자·익명·정상 사용·공개 의도 coverage. 소유자·비소유자·정상 사용은
  필수이며 익명·공개는 명시적인 해당 없음 사유를 대신 둘 수 있습니다.

이는 선언이지 인증된 사람 검토나 입증한 정책 정답이 아닙니다. 상태 코드·엄격한 JSON 타입·제한된
body로 `true`, `1`, `1.0`도 구분합니다. 일반 의존성 선언이나 소스 scope로 정답을 추론하지 않습니다.

`build_repository_http_verification_plan(request, response, cases)`는 현재 schema 2.0 요청·응답
전체를 검증합니다. 변경 제안에서는 모델의 중복 없는 header 배열을 명시적으로 map으로 정규화하고
GET method/path/headers를 지정 독립 사례와 정확히 대조합니다. 다르면 계획을 거부하며 모델에서
기대값을 만들거나 사례를 몰래 추가하지 않습니다. 검증한 no-change/unknown/refused는 사례 없이
`None`을 반환합니다.

`RepositoryHttpVerificationPlan`은 전체 요청·응답 식별자, 소스 전후 해시, HTTP 인터페이스,
전체 사례, 지정 회귀, 원래 PoC 해시와 정규화한 요청을 결합합니다. 정규화한 요청이 같아도 원래
header 배열 순서가 바뀌면 제안 식별자는 달라집니다. `validate_repository_http_verification_plan`은
전체 닫힌 계획을 다시 구성합니다.

## 요청만 전달하는 관찰과 제공 자료 비교

`prepare_repository_http_observer_schedule(..., phase="before" | "after")`는 모든 사례 ID와 요청만
투영하며 소스·정책·정답·모델 설명을 제외합니다. 종류는 `repository-http-observer-schedule`,
계획 ID는 `repository-http-verification-plan-*`입니다. 기존 schedule 진입점은 이를 거부합니다.

표준 라이브러리 전용 `_repository_http_transport`는 `validate_http_observer_schedule`,
`encode_http_observer_request`, `capture_repository_http_poc`를 제공합니다. 기존 제한된 HTTP
파서·시계 기본 요소는 그대로 공유하지만 새 schedule만 받습니다. 기본 소켓 구현은 없으며 신뢰하는
호출자가 연결된 stream과 시계를 주입해야 합니다.

- 고정 loopback `127.0.0.1:8765`, 리터럴 GET 경로와 허용한 합성 `test-*` 식별 헤더만 사용합니다.
- 최초 phase deadline 하나, 사례별 새 stream, redirect·재시도 없음과 framing/body/입출력 제한을 유지합니다.
- 전체 계획 분모를 결과에 남깁니다. 첫 오류 뒤 나머지는 미전송이며 획득한 stream은 만료·중단
  이후에도 각각 한 번 닫기를 시도하며 실패한 정리는 미확인으로 남깁니다.

원시 close 사실은 stream 정리이며 A/B guest 정리가 아닙니다. 획득 전 만료는 HTTP 전송이 아니므로
후속 host adapter는 setup/timeout 사실을 보존해야 합니다. callback은 신뢰하는 구성 요소이며 이
동기 codec으로 선점하지 못합니다. 결과는 계속 호출자가 제공한 미검증 자료입니다.

`decode_repository_http_phase_candidate`, `validate_repository_http_phase_candidate`는 별도
`RepositoryHttpPhaseCandidate`를 받습니다. 선언된 소스·인터페이스·사례·PoC 결합, 전체 순서의 관찰과
A/B 정리 값 `confirmed`, `unknown`, `failed`를 사용합니다. 오류 뒤에는
not-dispatched/phase-aborted suffix만 허용하며 T/pytest 필드·누락·순서 변경을 거부합니다.

`compare_repository_http_phase`는 호스트 기대값과 타입까지 비교합니다. 잘못된 frame도 전체
계획 분모를 유지합니다. 모든 값이 맞는 제공 frame도 `supplied-unverified`, 실행 `not-run`, 인가
`unknown`, `verified_fix=false`, `live_evidence=false`, `writes_authorized=false`입니다.
현재 직접 반환한 live phase를 대신하거나 패치를 승인하지 않습니다.

## 소스 전용 manifest와 A/B 선언

`_repository_http_manifest`는 평평한 소스 descriptor 하나와 HTTP 인터페이스를 위한 제한된
표준 라이브러리 codec입니다. 정책·정답·테스트·client fixture를 담지 않습니다. 입력 경로는
`/input/manifest.json`, `/input/project/<source.py>`입니다. 별도 live staging이 파일과 현재 세션을
측정하기 전까지 식별자와 해시는 선언입니다.

`_repository_http_runtime_profile`는 `RepositoryHttpRuntimeProfile`, `validate_runtime_profile`,
`build_container_create_plan`을 제공합니다. 마지막 함수의 결과는 실행기가 아닌
`RepositoryHttpCreatePlan` 데이터입니다.

| 역할 | 선언한 입력과 제한                                                                                                                  |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------- |
| A    | manifest·소스 readonly mount, network-none, 명시적 ASGI 앱·lifespan off·인증 override 없음, 메모리 512 MiB·CPU 1개·PID 64개.        |
| B    | 입력 mount 없음, 제한된 요청 전용 stdin·EOF, A의 네트워크만 공유하고 PID/mount namespace는 별도, 메모리 128 MiB·CPU 0.5개·PID 32개. |

새 guest root·이름·label, UID/GID 65532, readonly root, capability 제거, host port·인증정보·소켓
mount 없음과 제한된 임시 저장소를 선언합니다. phase 공유 40초 안에서 준비 시간도 소비하고 준비
누적 10초 제한을 추가하며 정리는 10초입니다. 계획 생성만으로 실제 강제를 주장하지 않습니다.

`runtime/repository_http/`에는 별도 guard·A/B 소스와 arm64 Dockerfile 두 개가 있습니다.
이미지 manifest는 해당 바이트·기존 의존성/base 참조·정규 recipe를 고정합니다. guest guard는
대상·도구 import보다 먼저이며 관찰자는 대상 import나 소스 읽기를 하지 않습니다.
상태는 계속 **declared-not-built**, 이미지 ID는 null, 준비·내용 검증은 false입니다.
수용한 이미지나 탈출 불가능한 격리라는 뜻이 아닙니다.

## 남은 연결

결정적인 보존 이미지 context·실제 내용 검사, 새 HTTP 전용 비공개 파일 checkpoint·봉인 staging,
Engine·중지 container 검사, 직접 host phase와 승인형 copy/before/diff/apply/after/restore 조작 흐름은
미완료입니다. 기존 파일 세션은 pytest 산출물을 요구하므로 가짜 테스트 필드로 수용할 수 없습니다.
원본 최종 적용·백업·편집 충돌 거부·복구는 #152/#150의 필수 조건입니다. 설치형 실제 수용과 저장 결과
GUI 연결도 후속이며 제공 자료·오프라인 통과로 완료하지 않습니다.
