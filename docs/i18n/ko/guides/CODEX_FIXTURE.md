<p align="center">
  <a href="../../../guides/CODEX_FIXTURE.md">English</a> ·
  <strong>한국어</strong>
</p>

# 명시적으로 선택하는 Codex 소유 fixture 검토

[문서 목차](../INDEX.md) · [오프라인 복사본 데모](FIXTURE_APPLICATION.md) · [AI 계약](../reference/AI_CONTRACT.md)

## 범위와 현재 근거

[#50](https://github.com/casing1/authzest/issues/50)은 유지하는 설정 fixture 하나를 위한 명령을
도입했습니다. 2026-09-12 `42ff108`에서 승인된 실제 CLI 검사 1회가 **PASSED**했습니다.
초안 검증, 별도의 정확한 문구 결정, 복사본 적용과 복구를 확인했습니다. 사용자 승인 범위에서
assistant가 문구를 입력했으며 독립적인 인간 승인 증명은 아닙니다. 발행된
[alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) POSIX 바이너리와 소스에서
제공하며 이전 alpha.2 바이너리에는 없습니다. 이 기능만으로 [#35](https://github.com/casing1/authzest/issues/35)를 완료하지 않습니다.

AuthZest의 작업·소스 payload에는 미리 보여 주는 패키지 내 `main.py` 스냅샷, 소스 근거, 선언 정책과
질문 하나를 포함합니다.
허용하는 소스 초안은 다른 모든 문자를 보존하며 `debug=True`를 `debug=False`로 바꾸는 것뿐입니다.
인가 finding, exploit PoC, 생성한 회귀 테스트나 검증된 보안 수정이 아닌 설정 시연입니다.
임의 저장소나 경로를 입력할 수 없습니다.

기본 `scan` 명령은 오프라인을 유지합니다. 기존 오프라인 제안·복사본 데모는 AI가 아닌 고정 응답을
사용합니다. 일반 저장소 AI 검토와 임의 패치는 지원하지 않습니다. #52의 선택적·별도 승인 소스 설정
검사가 기본값입니다. #54는 `--runtime-check`로 선택하는 고정 런타임 계획을 추가하며,
[런타임 안내](RUNTIME_VERIFICATION.md)에서 설명합니다. 어느 검사도 모델을 추가로 호출하지 않습니다.
#54의 제한된 실제 소스 환경 인수 검증은 통과했고 런타임 안내에 기록했습니다.
Alpha.3 발행과 공개 파일 검사는 별도로 통과했으며 [릴리스 기록](../releases/RELEASING.md)에 있습니다.
#35는 계속 열어두며 기존 alpha.2 태그·파일은 바뀌지 않습니다.

## 소스 또는 독립 실행 파일로 실행

설치한 소스 checkout 또는 [릴리스 안내](../releases/RELEASING.md#검증과-복구)에 따라 체크섬을
확인한 alpha.3 POSIX 실행 파일을 사용합니다. 내려받은 실행 파일이 PATH에 없으면 아래 `authzest`를
정확한 파일 경로로 바꾸세요. 바이너리는 Python 런타임과 fixture 의존성을 포함하지만 Codex나
계정 자격 증명은 포함하지 않습니다. 오프라인 `scripts.demo_*` 흐름에는 여전히 checkout이 필요합니다.

Codex가 관리하는 기존 ChatGPT 로그인과 신뢰하는 로컬 Codex **0.153.0** 설치본을 사용합니다.
adapter는 버전을 고정하며 다른 버전과의 호환성을 주장하지 않습니다. 실제 복사본 흐름은 POSIX
전용이고 기존 Windows 스캔 지원이 이 명령의 지원을 뜻하지 않습니다. Codex 계정에서 이용 가능한
모델을 고르세요. 아래의 `MODEL`은 자동 선택된 모델이 아닌 자리표시자입니다.

```bash
authzest codex-fixture --model MODEL --timeout-seconds 120
```

timeout 기본값은 120초입니다. 어떤 Codex 프로세스도 시작하기 전에 정확한 `HOST_INSTRUCTIONS`,
작업·소스 payload, 요청 모델과 요청 ID를 표시하고 해당 ID에 묶인 명시적 소스 공유 승인을 요구합니다.
Codex는 자체 harness 컨텍스트를 추가하므로 이 미리보기가 모델의 전체 컨텍스트를 보여 준다고
주장하지 않습니다. 표시된 `share <request_id>`
문구를 정확히 입력해야 해당 요청을 승인합니다. 이 단계에서 거절하거나 취소하면 제공자 프로세스를
시작하지 않습니다. 로그인 성공이 소스 전송·패치 적용·검증 실행 동의를
대신하지 않습니다.

기존 로그인은 Codex가 관리합니다. AuthZest는 API key, 토큰이나 자격 증명 파일을 읽지 않습니다.
Codex 로그인 동작은 공식 [인증 안내](https://learn.chatgpt.com/docs/auth)를 참고하세요.
[App Server 문서](https://learn.chatgpt.com/docs/app-server)는 관리형 ChatGPT 인증을 설명합니다.
여기서 정한 제한은 Codex 전체의 한계가 아닌 AuthZest의 더 좁은 fixture 흐름입니다.

## 최대 모델 한 턴과 별도의 파일 승인

공유 승인 이후 지원하는 로컬 App Server를 사용해 애플리케이션에서 최대 한 턴을 요청합니다.
요약의 `application_turn_attempts`는 adapter 호출 횟수이지 전송된 모델 턴이나 과금 횟수가 아닙니다.
`turn/start` 전에 사전검사에서 실패할 수 있습니다. AuthZest는 애플리케이션 재시도·fallback·모델
교체를 하지 않습니다. 다만 Codex 내부 transport
재시도는 발생할 수 있습니다. timeout은 토큰이나 금액의 강제 상한이 아니며 실패·취소 전에 사용량이
발생할 수 있습니다. 측정하지 못한 사용량은 미확인 상태로 남겨야 합니다.

같은 thread·turn의 `error`가 `willRetry: true`이고 인식하는 `responseStreamConnectionFailed`나
`responseStreamDisconnected` variant일 때만 기존 deadline·바이트·이벤트 한도 안에서 복구를
기다릴 수 있습니다. HTTP 상태는 없거나 null, `200`, `408`, `500`–`599`여야 합니다. 미리보기의
`max_accepted_retry_notifications: 3`은 관찰한 허용 알림 수를 제한하며 제공자 시도나 비용 상한이
아닙니다. 네 번째 알림, 다른 오류·치명적 오류, 인증·정책 실패, 잘못된 형식과 식별값·도구·컨텍스트
위반은 흐름을 중단합니다. 새 turn, 애플리케이션 재시도나 모델 교체를 요청하지 않습니다.

재시도 알림을 수용할 때마다 이전에 모은 최종 출력과 사용량을 폐기합니다. 성공하려면 새로운 최종
응답 검증과 정상 turn 완료가 필요하며 새 사용량 알림이 없으면 사용량은 미확인입니다.
`provider_retry_notification_count`는 초안 검증 성공 뒤에만 관찰한 알림 수를 기록합니다. 실패 시
`null`이며 0이나 제공자 시도·과금 횟수가 아닙니다. 공식
[App Server 오류 문서](https://learn.chatgpt.com/docs/app-server#errors)는 큰 오류 분류를 설명하지만
`willRetry`는 문서화하지 않습니다. wire 형식은 설치된 Codex 0.153.0에서 생성한
`ErrorNotification` 스키마를 기준으로 하며 AuthZest의 더 좁은 허용 규칙은 애플리케이션 정책입니다.

모델에 도구나 환경 접근을 제공하지 않고 도구 요청을 거부합니다. 출력은 비신뢰 JSON입니다.
호스트가 식별값과 소스 참조를 검증하고 정확히 유지하는 치환만 허용합니다. 유효한 JSON이나 올바른
소스 인용이 설명의 진실성을 입증하지는 않습니다. diff와 제안 식별값은 호스트가 만들며 모델 텍스트가
스스로 변경을 승인할 수 없습니다.

transport는 깨끗한 빈 작업 디렉터리에서 시작하고 ChatGPT 인증의 내장 OpenAI 제공자만 허용하며,
턴 전에 유효 도구·컨텍스트 설정을 확인합니다. 원격 제어 상태 조회와 이후 상태 알림은 `disabled`여야
하며 그렇지 않으면 흐름을 중단합니다. 프로토콜 출력은 줄마다 256 KiB, 합계 2 MiB로
제한하고 자체 프로세스 그룹을 정리합니다. 실행 오류는 비식별화하며 AuthZest는 원문 stderr,
계정 이메일이나 대화 transcript를 저장하지 않습니다. 이 제어는 신뢰하는 Codex 설치본을 전제로
하며 비신뢰 실행 파일을 격리하는 sandbox가 아닙니다.

관리형 ChatGPT 로그인의 모델 경로 선택은 Codex 내장 제공자에 맡기며, AuthZest가
`openai_base_url`로 API-key용 주소를 강제하지 않습니다. 두 사전 검사 모두 유효
`openai_base_url`이 null이 아닌 경우 공식 URL이나 빈 문자열도 거부하고 thread·turn 생성 전에
중단합니다. `OPENAI_BASE_URL` 환경변수도 전달하지 않습니다. 상속된 재지정은 설정 비호환이지
자격 증명 만료의 증거가 아니며, AuthZest가 사용자 Codex 설정을 편집하지 않습니다. 공식
[설정 안내](https://learn.chatgpt.com/docs/config-file/config-advanced)는 제공자 URL 재지정을
ChatGPT 로그인 설정과 별도로 설명합니다. 이 검사가 실제 네트워크 경로를 입증하지는 않습니다.

요청한 모델 식별값을 thread 시작 시 협의된 모델과 대조합니다. 요약에는
`model_identity_basis: negotiated-thread-model; not independently served-model attestation`을
기록합니다. 이는 응답을 실제 처리한 모델의 정체를 독립적으로 입증한 것이 아닙니다.

인식하는 일반 `warning` 알림은 크기가 제한된 비권위적 메타데이터입니다. 요약에는 초안 검증에 성공한
뒤에만 관찰한 `provider_warning_count`를 기록하며 경고 원문은 기록하지 않습니다. 다른 경로는 0이
아닌 `null`(미확인)을 유지합니다. 경고로 설정을 바꾸거나 도구를 허용하거나 공유·적용을
승인하거나 사용량을 제공할 수 없습니다. 형식이 잘못된 경고, `configWarning`, `guardianWarning`,
허용 조건에 맞지 않는 오류와 알 수 없는 알림 종류는 여전히 흐름을 중단합니다.

`thread/settings/updated`는 합의한 thread 경계와 별도로 대조합니다. 모델·제공자, 작업 디렉터리,
승인 정책·검토자, 네트워크가 비활성인 읽기 전용 sandbox, 추론 노력과 collaboration mode의
모델·추론·지침 설정을 확인합니다. 불일치하면 흐름을 중단하며 안내용 경고로 검사를 면제할 수 없습니다.

유효한 초안은 별도의 정확한 diff 결정 대상으로 표시됩니다. 승인을 받아도 새로 만든 비공개 fixture
복사본만 바꾸고 원본 checkout은 편집하지 않습니다. 표시된 `apply <proposal_id>` 문구를 정확히
입력해야 하며 거절·취소하면 초안을 적용하지 않습니다. 적용 후 선택한 검사—기본 소스 설정 또는
명시적으로 선택한 소유 fixture 런타임—는 선택 사항이며 별도 승인이 필요합니다.
복구에는 `restore <proposal_id>`가 필요하고
이후 변경을 발견하면 거부하여 사용자 작업을 덮어쓰지 않습니다. 복사본, 전후 스냅샷과 `record.json`은
확인할 수 있도록 남기며 워크플로 JSON 요약에는 요청·제안 ID와 확인 가능한 사용량을 포함합니다.
[복사본 적용 안내](FIXTURE_APPLICATION.md)의
파일 작업 한계와 실패 의미가 그대로 적용됩니다.

## 선택적 소스 설정 검사 (기본값)

복사본 적용 후 복구 전에 #52가 고정 계획을 표시하고 정확한 `verify <plan_id>` 문구를 요구합니다.
공유나 적용 승인이 이 단계를 승인하지 않습니다. 계획은 제안, 적용된 소스 식별값과 유지하는
검사·worker 식별값에 묶입니다. 검사 ID는 `owned-fixture-debug-disabled-v1`이며 미리보기에는 정확한
worker 소스, SHA-256과 제한값이 포함됩니다. 터미널 선택은 기록된 결정이지 인증된 인간 승인 증표가 아닙니다.

고정 worker는 별도 자식 프로세스에서 시작·입출력 deadline 5초, 별도의 종료·회수 정리 한도 1초,
입력 1 KiB와 출력 4 KiB 한도로 동작합니다. 계획에는 `max_cleanup_seconds`가 포함됩니다.
호스트는 적용된 복사본을 재확인하고 불변 `main.py` 바이트를 worker에 전달합니다. 고정 검사기는
유지하는 소스의 고정 해시만 허용한 뒤 바이트를 AST로 파싱하고 선언된 `FastAPI(debug=False)` 설정을
검사합니다. 별도 프로세스가 OS·네트워크 sandbox를 뜻하지 않습니다.
소스를 import하거나
실행하지 않고 서버·테스트·설치 hook을 실행하지 않으며 모델이 만든 명령을 받거나 제공자를 호출하지
않습니다. 통과는 이 제한된 소스 설정 검사를 뜻할 뿐 런타임 동작, 인가의 정확성이나 보안 수정 효과의
검증을 뜻하지 않습니다.

worker는 축소한 환경을 받습니다. frozen main 프로세스에서만 기존 `_PYI_ARCHIVE_FILE`,
`_PYI_APPLICATION_HOME_DIR`, `_PYI_PARENT_PROCESS_LEVEL`이 실제 존재하는 현재 실행 파일,
실제 존재하는 `sys._MEIPASS` 디렉터리, level `1`과 일치하는지 확인한 뒤 값 그대로 보존합니다.
bootloader 상태를 새로 만들지 않습니다. 이는 내부 값의 일관성 확인이지 실행 파일·환경의 신뢰성
인증이 아닙니다. 소스 모드 worker는 여전히 이 외부 환경값들을 제외합니다. deadline 5초와 별도
정리 한도 1초는 바뀌지 않습니다.

이 기본 모드는 `verification_scope: source-configuration`과 `passed`, `failed`, `not-run` 중 하나인
`verification_status`를 보고하며 해당 모드의 `runtime_verification_status`는 항상 `not-run`입니다. 정상적으로
만든 계획 기반 `verification` 기록은 범위, 계획·검사·worker·소스 식별값, 사유, 경과 시간과 종료 상태를
담습니다. 예기치 못한 워크플로 실패에서는 결과 세부 정보가 누락될 수 있습니다. 누락을 성공이나
`not-run`으로 추정하지 말고 보존된 기록을 확인하세요.
거절·취소하면 worker를 시작하지 않고 `not-run`으로 기록합니다. 다른 워크플로 단계가 실패하지 않으면
의도적인 건너뛰기의 CLI 종료는 `0`입니다.
worker 실패, 오래된 상태나 journal 실패는 검증된 결과가 아닌 종료 `1`을 냅니다. 건너뛰거나 실패해도
안전할 때 별도의 복구 결정을 계속 제시합니다. 복구는 자동이 아니며 보존된 검사 결과를 바꾸지 않습니다.
그 결과는 복구한 파일이 아닌 적용 당시의 소스 해시를 설명합니다. 적용·검사·복구 결과는 별개입니다.
journal 스키마 `1.1`은 기록에 성공하면 전체 `verification_plan` 미리보기, 결정과 결과를 보존합니다.
`journal_status: recorded`는 호스트 쓰기의 완료를 뜻하며 인증이나 영구 보존의 증명이 아닙니다.
쓰기·fsync 오류는 `unconfirmed`가 되고 실패 기록으로의 수정을 최선 노력 방식으로 시도합니다.
이 수정도 실패하면 남은 기록은 불확실할 수 있습니다. 이전 성공 항목만 믿지 말고 실제 파일과 보고된
실패를 확인하세요. journal로 세션을 재시작·재개할 수 없으며 재사용을 방지하는 승인 증표도 아닙니다.

기존 `scripts.demo_apply` 흐름은 바뀌지 않고 `not-run`을 유지합니다. #52의 소스 전용 추가 기능만으로
#35의 별도 승인 런타임 검증과 실패·복구 완료 조건을 충족하지는 않습니다.

## 명시적으로 선택하는 소유 fixture 런타임 검증

#54 런타임 계획을 명시적으로 선택합니다. 소스 설치에는 [런타임 안내](RUNTIME_VERIFICATION.md)의
선택 의존성이 필요하며 alpha.3 POSIX 바이너리에는 포함되어 있습니다.

```bash
authzest codex-fixture --model MODEL --timeout-seconds 120 --runtime-check
```

옵션 선택은 소스 공유·변경 적용·검증 실행 승인이 아닙니다. 적용 후 같은 별도 `verify <plan_id>`
결정이 필요합니다. 고정 worker는 정확히 유지하는 fixture 전후 버전만 허용하고 일치하는 번들 상수를
실행합니다. `app.debug`와 메모리 내 ASGI `GET /health`를 관찰하며 의존성 버전도 관측값으로 기록합니다.
임의 소스 경로나 모델이 만든 명령을 받지 않고 TCP/UDP 서버를 시작하지 않습니다. OS·네트워크
sandbox, 인가 검사, exploit 재현이나 검증된 보안 수정이 아닙니다.

런타임 세션은 `verification_scope: owned-fixture-runtime`과 journal 스키마 `1.2`를 사용합니다.
`runtime_verification_status`는 기록된 검사를 반영하며, 예기치 못한 중단에서는 실행하지 않았다고
추정하지 않도록 불확실한 상태를 생략할 수 있습니다. 누락된 의존성을 자동 설치하지 않습니다.
`runtime-dependency-unavailable`은 `not-run`이며 의도적인 거절·취소와 달리 CLI 종료 `1`입니다.
복구는 여전히 독립적이고 보존된 결과는 복구한 파일이 아닌 검사한 적용 해시를 설명합니다.
#54의 제한된 실제 소스 환경 인수 검증은 통과했으며 근거는 [런타임 안내](RUNTIME_VERIFICATION.md)에
기록했습니다. 별도로 검증한 alpha.3 발행은 [릴리스 안내](../releases/RELEASING.md)에 있으며
일반 저장소 지원이나 #35 완료의 근거는 아닙니다.

## 오프라인 설정 검사 데모

editable 개발 환경 설치 후 저장소 루트에서 실행합니다.

```bash
python -m scripts.demo_verify
```

소스 checkout 전용 데모이며 호출자가 작성한 mock 초안을 사용하고 Codex나 모델을 호출하지 않습니다.
새 비공개 fixture 복사본에 별도의 정확한 `apply <proposal_id>`, `verify <plan_id>`,
`restore <proposal_id>` 결정을 제시하고 같은 고정 설정 worker를 사용합니다. 표시된 ID를 따르세요.
기본 승인되는 단계는 없습니다. 데모 통과는 오프라인 흐름의 근거이지 실제 모델 성능, 대상 코드 실행이나
보안 수정 효과 검증이 아닙니다. 확인할 수 있도록 복사본과 기록을 남깁니다.

같은 오프라인·호출자 작성 mock 흐름에서 런타임 worker를 선택하려면 다음을 실행합니다.

```bash
python -m scripts.demo_verify --runtime-check
```

이 버전도 제공자 호출은 0회이지만 별도 검증 승인 뒤 정확히 유지하는 fixture를 실행합니다.
선택 의존성이 필요하고 [런타임 안내](RUNTIME_VERIFICATION.md)의 경계를 따릅니다.
새로운 실제 모델 검사의 근거가 아닙니다.

## 계약 호환성

AI 스키마 `1.1`은 `temperature: null`을 허용하며 숫자 sampling temperature를 요청하지 않고
제공자가 관리한다는 뜻입니다. 기존 숫자 temperature 요청은 스키마 `1.0`, 기존 식별값과
`AdapterConfig` 기본값 `0.0`을 유지합니다. null은 0이나 결정론적 생성을 뜻하지 않습니다.
스캔 리포트는 스키마 `1.2`를 유지하며 이 변경이 패키지 버전 변경이나 새 릴리스를 뜻하지 않습니다.

실제 시도, end-to-end 결과, 토큰 사용량과 실패 복구 근거는 오프라인 mock과 별도로 기록해야 합니다.
미확인 사용량은 0이 아니며 mock 성공만으로 실제 end-to-end 성공을 입증하지 않습니다.
아래 날짜별 이력은 이후 갱신된 pending/Draft 기록을 포함하여 각 단계 당시의 상태를 보존합니다.
아래 성공한 실제 검사는 #52 이전 기록이며, 이후 오프라인 작업은 별도로 표시합니다.

## 이전 개발 검증 — 2026-09-11

로컬 Python 3.12.7에서 신규 394개를 포함한 테스트 1,129개가 112.99초에 통과했습니다. transport
부분은 실제 fake 서버 자식 프로세스와 CLI 승인/복구·거절 흐름을 포함한 오프라인 테스트 242개입니다.
timeout·취소 검사에서 테스트 wrapper와 하위 프로세스의 종료를 확인했습니다.
문서 검사기 테스트 14개, 언어·링크 검사, Ruff, frontend lint/format/build도 통과했습니다.
재빌드한 wheel과 macOS ARM64 개발 실행파일에서 명령 노출과 공유 전 EOF 취소를 확인했습니다.
native inventory smoke는 선택한 바이너리와 경로를 옮긴 복사본에서 14개 검사를 통과했으며 Codex나
대상 소스를 실행하지 않았습니다. 이 산출물은 배포하지 않았으며 기존 로컬 빌드 의존성을 사용했습니다.

Codex 0.153.0의 메타데이터 전용 사전검사에서 ChatGPT 로그인, 원격 제어 비활성화,
상속된 MCP 서버 2개 비활성화, 지침 소스·런타임 작업공간 root가 없는 새 읽기 전용 thread를
확인했습니다. **모델 turn은 0개**이며 fixture 소스를 보내지 않았습니다. 실제 모델 생성은
**PENDING**으로 남아 있고, 이 검사들이 실제 end-to-end 성공이나 검증된 수정을 뜻하지는 않습니다.

## 승인된 실제 시도 — 2026-09-11

이는 제한적 동일 turn 복구 변경 전인 `807ada2`까지의 과거 기록입니다.
사용자는 처음 최대 3회의 실제 시도를 승인했고 이후 2회를 추가 승인했습니다. 승인된 호스트 시도
5회를 모두 사용했지만 이것이 모델 턴 5회 전송이나 과금을 입증하지는 않습니다. 유효한 초안은
생성하지 못했습니다. 1–4번째 시도는 경고·설정 메타데이터 호환성 검사에서
중단되었습니다. 위 명시적 승인 한도 안의 검증 시도이지 애플리케이션 재시도나 이후 호출 허용이 아닙니다.

5번째 시도는 제한된 일반 경고를 비권위적 메타데이터로 수용한 뒤
`codexErrorInfo: responseStreamDisconnected`, `willRetry: true`인 Codex 오류를 받았습니다.
adapter는 비식별화된 `Unexpected Codex event` 실패로 중단했습니다. 기록된 로컬 지연은
`12357.580 ms`입니다. 제공자의 재시도 표시는 재시도 완료를 입증하거나 AuthZest의 추가 호출을
허용하지 않습니다. Codex 내부 재시도에는 AuthZest가 강제하는 횟수 상한이 없습니다.

5회의 사용량은 모두 미확인이며 초안 성공 경로의 경고 개수도 기록하지 못했습니다.
실제 사람 승인 적용·복구 흐름에 도달하지 못했고 파일 적용이나
복구가 발생하지 않았으며 원본 checkout은 변경되지 않았습니다. 위 fake 서버 승인·복구 테스트는
별도 근거이지 실제 연동 성공 시연이 아닙니다. `verification_status`는 `not-run`, 실제 end-to-end
검증은 **PENDING**이며 [PR #51](https://github.com/casing1/authzest/pull/51)은 병합·릴리스 없이
draft 상태를 유지합니다. 남은 실제 시도 승인은 없으며 추가 호출에는 새로운 사용자 승인이 필요합니다.

## 오프라인 후속 작업 — 2026-09-12

이 오프라인 후속 구현과 테스트는 **실제 호출 0회**로 진행했습니다. Python 3.12.7에서 1,171개 테스트가
153.54초에 통과했으며 이전 1,129개 실행 이후 42개를 추가했습니다. transport 테스트는 276개(+34),
CLI 테스트는 66개(+8)입니다. Ruff, frontend lint/format/build, 문서 검사기 테스트 14개와 언어·링크
검사가 통과했습니다.

재빌드한 native 바이너리는 경로를 옮긴 복사본을 포함하여 기존 명령당 45초 제한에서 inventory
검사 14개를 모두 통과했습니다. 독립적인 wheel/native 산출물 검사는 동일한 30초 제한에서 명령
도움말, 공유 전 EOF 취소, 재시도 알림 한도 `3`과 미확인(`null`) 재시도 카운터를 확인했습니다.
앞선 병렬 산출물 검사 한 번은 30초 timeout에 도달했으며 원인은 확정하지 않았습니다. 이 검사들은
Codex나 대상 소스를 실행하지 않았습니다. 원본 fixture 해시와 깨끗한 main checkout은 변경되지
않았으며 산출물을 배포하지 않았습니다.

이 오프라인 결과는 과거 실패 5회를 성공으로 바꾸거나 추가 실제 시도를 허용하지 않습니다.
실제 end-to-end 검증은 **PENDING**이고 PR #51은 draft를 유지합니다.

## 새로 승인된 실제 시도 — 2026-09-12

`ca97ab1`에서 새로 승인된 호스트 시도 1회(최대 120초, 같은 fixture·로그인)는 `11610.537 ms` 후
`draft-failed`/종료 `1`로 끝났습니다. 진단 관찰에서 `responseStreamDisconnected`, 중첩 HTTP `401`,
`willRetry: true`를 확인했으며 production은 `Codex reported a non-recoverable HTTP status`로
정상 중단했습니다. 재시도 표시가 인증 거절을 무시할 수는 없습니다. 반환 식별값, 사용량, 경고·재시도
개수, 적용과 복구는 모두 `null`, `verification_status`는 `not-run`이며 독립 해시 검사로 원본 보존을
확인했습니다. 이후 Codex 0.153.0은 저장된 ChatGPT 로그인을 보고했지만 서버 수락을 입증하지는
않습니다. 자격 증명 만료·할당량 소진·모델 이용 불가를 확정하지 않았고 로그아웃·재인증·API key 변경이나
추가 시도도 하지 않았습니다. 새 1회 승인은 소진되었으며 총 6회의 승인된 호스트 시도가 초안 검증 전에
실패했습니다. 이것이 6회 과금을 입증하지는 않습니다. 실제 검증은 **PENDING**, PR #51은 draft이며
병합이나 새 호출 승인은 없습니다.

## 사용자 재인증 이후 — 2026-09-12

사용자가 다시 로그인했습니다. CLI 로그인 상태와 읽기 전용 App Server `account/rateLimits/read`
조회는 모델 turn이나 fixture 소스 전송 없이 성공했습니다. 이후 사용자가 같은 fixture,
`gpt-6-astra`, 관리형 ChatGPT 계정과 120초 제한으로 추가 1회를 승인했습니다.
`573f7a3`(실행 코드는 `ca97ab1`과 동일)에서 `11086.934 ms` 후
`responseStreamDisconnected`, 중첩 HTTP `401`, `willRetry: true`로 실패했습니다. 어댑터는 중단했고
`status: draft-failed`, 종료 `1`, 식별값·사용량·경고·재시도·적용·복구 필드의 null과
`verification_status: not-run`을 유지했습니다. 원본 fixture 해시도 그대로입니다.
총 7회의 승인된 호스트 시도가 모두 초안 검증 전에 끝났으며, 이는 과금된 turn 횟수가 아닙니다.

점검 결과 AuthZest가 ChatGPT 로그인을 요구하면서 내장 모델 제공자 주소를
`https://api.openai.com/v1`로 강제하고 있었습니다. 계정 조회 성공과 생성 실패는 경로 불일치와
부합하지만, 401의 정확한 원인은 **확정하지 않았습니다**. 강제 재지정을 제거하고 상속된 재지정은
사전 검사에서 거부하도록 수정했습니다. 설치된 0.153.0 App Server가 수정된 경계를 수용했고
계정·한도 메타데이터 조회도 성공했으며, 이때도 모델 turn은 0회이고 fixture 소스는 보내지
않았습니다. AuthZest가 자격 증명이나 사용자 설정을 변경하지 않았습니다.

수정된 소스는 새 주소 관련 사례 32개를 포함한 오프라인 Python 검사 1,203개
(transport 합계 308개), Ruff와 문서 검사 14개를 통과했습니다. 별도의 제한된 transport 실행에서
기존 하위 프로세스 정리 검사 2개가 `ps`를 실행하지 못했으나, 필요한 로컬 프로세스 권한으로
조건을 바꾸지 않고 재검사하여 통과했고 전체 검사도 통과했습니다. 테스트 timeout이나 assertion을
완화하지 않았습니다. 이전 wheel/native 산출물 검사는 이번 수정 이전의 결과입니다.

이 경로 수정 이후 모델 생성은 수행하지 않았습니다. 추가 1회 승인은 소진되었으며 8번째 시도,
병합·릴리스는 하지 않았습니다. PR #51은 draft, #35는 열린 상태를 유지합니다.

## 승인된 CLI 검사 성공 — 2026-09-12

같은 공개 fixture, 관리형 ChatGPT 계정, `gpt-6-astra`, 120초 제한으로 추가 1회를 새로 승인받은 뒤
실행 코드 커밋 `42ff1082d6059516b865c2db1b0ebce7ce997763`에서 검증된 초안을 받았습니다.
초안 단계는 `13580.995 ms` 걸렸으며 보고된 사용량은 `input_tokens: 5573`, `output_tokens: 315`,
관찰 횟수는 `provider_warning_count: 1`, `provider_retry_notification_count: 0`입니다.
이는 이번 성공의 제공자 보고 사용량이지 이전 실패까지 합한 총량이나 독립 검증된 과금 기록이 아닙니다.
모델 식별값은 여전히 thread에서 협의된 메타데이터이며 실제 처리 모델의 독립 증명이 아닙니다.

assistant가 호스트에서 만든 한 줄 diff를 검토하고, 사용자가 승인한 E2E 검사 범위에서 별도의
정확한 적용·복구 문구를 입력한 뒤 `status: completed` / 종료 `0`을 확인했습니다. 같은 제안과
새 비공개 복사본의 적용 결과는 `applied: true`, 복구 결과는 `restored: true`입니다.
이 CLI 선택은 결정 흐름을 시연한 것이며 독립적인 인간 검토나 인증된 사용자 승인 증표가 아닙니다.

- 요청: `request-a04278a94923c955b1e807ee2cd81a1b8b4a062da58f3e7e371b3e2a4ffce34a`.
- 제안: `proposal-ce153ad1b2ba0b6b427e324403bb127c07aca830ad728e00c68e77a20c34ea04`.
- 변경 전·복구 후 SHA256: `c10770594e77cd1c1ec93c19ef2b810aea34ed873d8dbf392b57e50a1c2729df`.
- 적용 후 SHA256: `e010818e7259ad5c1ebfc5dfcb6dc046100376c778a70d0657d7ebb1ed7fdcfe`.

복구 직전 직접 해시 검사로 적용된 바이트를 확인했습니다. 이후 독립적인 읽기 전용 점검에서
복구된 파일, 전후 스냅샷, journal 상태·결정과 변경되지 않은 원본·작업 트리 fixture 해시를 대조했습니다.
journal에는 적용 후 복구가 기록되었으며 스냅샷과 함께 호스트가 만든 비공개 임시 작업 폴더에
남아 있습니다. 이 기록에 자격 증명이나 계정 프로필은 포함하지 않았습니다.

전체 승인된 호스트 시도로는 8번째이며 이전 실패 7회와 이번 성공 1회를 뜻합니다. 과금되거나
전송된 제공자 turn 수를 뜻하지 않습니다. 애플리케이션 재시도나 추가 모델 호출은 없었습니다.
경로 수정 이후 첫 시도가 이전 401 없이 통과한 것은 경로 진단을 뒷받침하지만 이전 HTTP 요청을
독립 추적한 것은 아닙니다. 이번 승인은 소진되었으며 릴리스를 뜻하지 않습니다.
이 #51 실행 기록은 `verification_status: not-run`이었으며 이후 #52의 소스 설정 검사를 실행한
기록이 아닙니다. 당시 스냅샷에서는 소스·테스트 실행, 보안 수정 효과 검증, 일반 저장소 AI와 남은
#35 작업을 구현하지 않은 상태였습니다.

고정한 `42ff108` 실행 코드 스냅샷으로 개발용 wheel과 macOS ARM64 산출물을 다시 빌드했습니다.
두 산출물 모두 도움말·전체 미리보기·공유 전 EOF 취소를 Codex 프로세스와 모델 turn 없이 통과했고,
선택한 native 실행 파일과 이동 복사본의 inventory smoke 14개도 통과했습니다. 산출물 명령별 30초,
inventory 명령별 45초 제한을 유지했습니다. native 검사 한 번은 호스트 sandbox의 semaphore 제약에
막혔으나 필요한 로컬 권한으로 같은 조건에서 통과했습니다. 배포하지 않은 개발 빌드이며 로컬
의존성을 재사용했습니다. 새 기기 설치·업그레이드·서명·공증·다른 OS 지원이나 패키지 산출물에서의
실제 모델 실행을 입증하지는 않습니다.

## 소스 설정 검사 확장 — 오프라인 검증, 2026-09-12

#52 실행 코드 `52311f99a28711d7d362cfd313a7dfde8571f785`에서 테스트 1,350개가 152.04초에
통과했습니다. Ruff lint·포맷(Python 124개 파일), frontend clean install/lint/format/build,
문서 검사기 테스트 14개와 Markdown 36개 / 언어쌍 17개 / 링크 460개 / shell 블록 82개 검사도
통과했습니다. 워크플로 검사는 오프라인 fixture와 mock만 사용하며 실제 Codex·계정·모델·제공자 네트워크 호출은 없습니다.

소스 checkout 터미널 데모에서 fixture 변경 적용, `23.572 ms`의 고정 AST 설정 검사 통과와 복사본
복구를 확인했습니다. 독립 검사로 위에 기록한 적용·복구 해시와 원본 보존을 확인했습니다.
assistant가 검사 범위에서 정확한 문구를 입력했으며 독립적인 인간 승인이나 새로운 실제 모델 결과가 아닙니다.

재빌드한 macOS ARM64 개발 바이너리(SHA256
`b86d7da8c33bb61ffb073dc6396aaf4cbae90f845dd3b01bde4d59a80d3ebc55`)에서 fake Codex 서버를
사용해 실제 부모→worker 흐름을 통과했습니다. 공유·적용·검사·복구를 별도로 결정했고 종료 `0`,
빈 stderr를 확인했습니다. 초기 시작은 외부 30초 제한 안인 14.732초, 자식 검사는 그대로인
deadline 5초와 별도 정리 한도 1초 안인 `131.652 ms`였습니다. 전체 흐름은 15.399초 걸렸습니다.
실제 복사본 적용·복구와 원본 보존도 독립 확인했습니다. 가짜 식별값과 토큰 필드는 고정 테스트 데이터이며
제공자 사용량이 아닙니다.

이전 cold worker 시작은 5초에서 두 번 timeout이 났고 병렬 도움말 검사도 30초 제한에 걸렸으나
독립 재검사에서는 통과했습니다. 위의 최소 bootloader 컨텍스트 대조·유지 수정으로 제한을 완화하지
않고 패키지 worker 시작 문제를 해결했습니다. 최종 검사 harness는 한 번 호스트 semaphore 제약으로
애플리케이션 시작 전에 중단됐고, 필요한 IPC 권한으로 같은 조건에서 통과했습니다.
같은 최종 바이너리의 inventory 전용 smoke 14개(선택본 7개, 이동본 7개)가 기존 명령별 45초 제한으로
통과했고 도움말도 30초 안에 통과했습니다. native 설정 검사 근거는 적용된 `debug=False` 소스에
한정되며 변경 전 상태의 native 실패 검사를 뜻하지 않습니다.

배포하지 않은 로컬 개발 산출물이며 새 기기·다른 플랫폼·서명·업그레이드·실제 모델 패키지 검증을
뜻하지 않습니다. #52 소스 설정 검사의 완료 조건은 충족했으며 해당 과거 실행의 런타임 검증은
`not-run`으로 남았습니다. #35는 계속 열어둡니다. 새 릴리스나 검증된 보안 수정을 주장하지 않습니다.
