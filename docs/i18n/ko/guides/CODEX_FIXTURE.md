<p align="center">
  <a href="../../../guides/CODEX_FIXTURE.md">English</a> ·
  <strong>한국어</strong>
</p>

# 명시적으로 선택하는 Codex 소유 fixture 검토

[문서 목차](../INDEX.md) · [오프라인 복사본 데모](FIXTURE_APPLICATION.md) · [AI 계약](../reference/AI_CONTRACT.md)

## 범위와 현재 근거

[#50](https://github.com/casing1/authzest/issues/50)은 유지하는 설정 fixture 하나를 위한 소스 checkout
명령을 추가합니다. 실제 end-to-end 검증은 **PENDING**입니다. 배포된 alpha.2 바이너리에는 없으며
이 기능만으로 [#35](https://github.com/casing1/authzest/issues/35)를 완료하지 않습니다.

AuthZest의 작업·소스 payload에는 미리 보여 주는 패키지 내 `main.py` 스냅샷, 소스 근거, 선언 정책과
질문 하나를 포함합니다.
허용하는 소스 초안은 다른 모든 문자를 보존하며 `debug=True`를 `debug=False`로 바꾸는 것뿐입니다.
인가 finding, exploit PoC, 생성한 회귀 테스트나 검증된 보안 수정이 아닌 설정 시연입니다.
임의 저장소나 경로를 입력할 수 없습니다.

기본 `scan` 명령은 오프라인을 유지합니다. 기존 오프라인 제안·복사본 데모는 AI가 아닌 고정 응답을
사용합니다. 일반 저장소 AI 검토, 임의 패치와 검증 실행은 이 명령에서 구현하지 않습니다.

## 현재 소스에서 실행

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

## 모델 한 턴과 별도의 파일 승인

공유 승인 이후 지원하는 로컬 App Server를 시작하고 애플리케이션에서 한 턴을 요청합니다.
AuthZest는 애플리케이션 재시도·fallback·모델 교체를 하지 않습니다. 다만 Codex 내부 transport
재시도는 발생할 수 있습니다. timeout은 토큰이나 금액의 강제 상한이 아니며 실패·취소 전에 사용량이
발생할 수 있습니다. 측정하지 못한 사용량은 미확인 상태로 남겨야 합니다.

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

요청한 모델 식별값을 thread 시작 시 협의된 모델과 대조합니다. 요약에는
`model_identity_basis: negotiated-thread-model; not independently served-model attestation`을
기록합니다. 이는 응답을 실제 처리한 모델의 정체를 독립적으로 입증한 것이 아닙니다.

유효한 초안은 별도의 정확한 diff 결정 대상으로 표시됩니다. 승인을 받아도 새로 만든 비공개 fixture
복사본만 바꾸고 원본 checkout은 편집하지 않습니다. 표시된 `apply <proposal_id>` 문구를 정확히
입력해야 하며 거절·취소하면 초안을 적용하지 않습니다. 복구에는 `restore <proposal_id>`가 필요하고
이후 변경을 발견하면 거부하여 사용자 작업을 덮어쓰지 않습니다. 복사본, 전후 스냅샷과 `record.json`은
확인할 수 있도록 남기며 워크플로 JSON 요약에는 요청·제안 ID와 확인 가능한 사용량을 포함합니다.
[복사본 적용 안내](FIXTURE_APPLICATION.md)의
파일 작업 한계와 실패 의미가 그대로 적용됩니다.

모든 결과는 `verification_status: not-run`을 유지합니다. 소스 코드, 테스트 명령, 설치 hook이나
검증 계획을 실행하지 않습니다. 초안이나 파일 치환 성공은 검증된 수정이 아닙니다. 완전한 #35의
완료 조건을 충족하려면 이후 이슈에서 별도 승인한 제한적 검증을 추가해야 합니다.

## 계약 호환성

AI 스키마 `1.1`은 `temperature: null`을 허용하며 숫자 sampling temperature를 요청하지 않고
제공자가 관리한다는 뜻입니다. 기존 숫자 temperature 요청은 스키마 `1.0`, 기존 식별값과
`AdapterConfig` 기본값 `0.0`을 유지합니다. null은 0이나 결정론적 생성을 뜻하지 않습니다.
스캔 리포트는 스키마 `1.2`를 유지하며 이 변경이 패키지 버전 변경이나 새 릴리스를 뜻하지 않습니다.

실제 계정·모델 이용 가능 여부, end-to-end 결과, 토큰 사용량과 실패 복구 근거는 명시적인 실제 검증
이후 기록해야 합니다. 오프라인 mock이나 이 문서만으로 확인된 사항이 아닙니다.

## 개발 검증 — 2026-09-11

로컬 Python 3.12에서 신규 222개를 포함한 테스트 957개가 통과했습니다. transport 부분은
실제 fake 서버 자식 프로세스와 CLI 승인/복구·거절 흐름을 포함한 오프라인 테스트 85개입니다.
timeout·취소 검사에서 테스트 wrapper와 하위 프로세스의 종료를 확인했습니다.
문서 검사기 테스트 14개, 언어·링크 검사, Ruff, frontend lint/format/build도 통과했습니다.
wheel과 macOS ARM64 개발 실행파일에서 명령 노출과 공유 전 EOF 취소를 확인했습니다.
이 산출물은 배포하지 않았으며 기존 로컬 빌드 의존성을 사용했습니다.

Codex 0.153.0의 메타데이터 전용 사전검사에서 ChatGPT 로그인, 원격 제어 비활성화,
상속된 MCP 서버 2개 비활성화, 지침 소스·런타임 작업공간 root가 없는 새 읽기 전용 thread를
확인했습니다. **모델 turn은 0개**이며 fixture 소스를 보내지 않았습니다. 실제 모델 생성은
**PENDING**으로 남아 있고, 이 검사들이 실제 end-to-end 성공이나 검증된 수정을 뜻하지는 않습니다.
