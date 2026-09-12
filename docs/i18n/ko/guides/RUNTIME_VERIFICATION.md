<p align="center">
  <a href="../../../guides/RUNTIME_VERIFICATION.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소유 fixture 런타임 검증

[문서 목차](../INDEX.md) · [Codex fixture](CODEX_FIXTURE.md) · [복사본 적용](FIXTURE_APPLICATION.md)

## 범위

[#54](https://github.com/casing1/authzest/issues/54)는 관리하는 설정 예제에 opt-in 런타임 검사를
추가합니다. 발행된 alpha.2 바이너리에는 포함되지 않습니다. 일반 `scan`은 계속 오프라인 소스
검사이며 기존 소스 설정 검증이 기본값입니다. `--runtime-check`는 다른 검사 계획을 선택할 뿐,
실행 권한을 부여하지 않습니다.

내장 `main.py`의 정확한 두 버전만 허용합니다. 바이트 단위 일치 확인 후 대응하는 내장 상수
코드만 실행하며 호출자가 선택한 경로, 임의 입력 프로그램, 모델 생성 테스트나 명령은 실행하지
않습니다. 지원하는 변경은 `debug=True` → `debug=False`뿐입니다. 생성된 앱의 `debug` 불리언과
프로세스 내부 ASGI `GET /health` 한 번을 검사하며 HTTP 200 및 JSON `{"status":"ok"}`를
기대합니다. 악용 재현은 수행하지 않습니다.

이는 정상 설정·health smoke이며 **인가 정확성, 취약점 재현 또는 보안 수정 검증이 아닙니다**.
인증, 객체 소유권, lifespan hook, 실제 HTTP 서버, 다른 경로나 일반 FastAPI 호환성을 검사하지 않습니다.

## 실행

신뢰하는 Python 3.12 소스 환경에서 선택 의존성을 명시적으로 설치합니다.

```bash
python -m pip install -e '.[fixture]'
authzest codex-fixture --model MODEL --timeout-seconds 120 --runtime-check
```

`MODEL`은 계정에서 사용할 수 있는 모델을 명시적으로 선택하는 자리이며 자동 대체 모델이 아닙니다.
Codex 경로에는 [Codex 안내](CODEX_FIXTURE.md)의 버전과 관리형 ChatGPT 로그인이 필요합니다.
소스 공유는 구독 사용량을 소비할 수 있지만 런타임 검사 자체는 모델을 호출하지 않습니다.
검증 중 의존성을 자동 설치하지 않으며 필요한 의존성이 없으면 `not-run` 및
`runtime-dependency-unavailable`을 반환하고 워크플로는 검증 미완료로 처리합니다.

호출자가 작성한 모의 초안을 쓰며 **제공자를 전혀 호출하지 않는** 개발 checkout 데모입니다.

```bash
python -m scripts.demo_verify --runtime-check
```

`--runtime-check`를 생략하면 기존 소스 설정 검사를 사용합니다. 한 세션은 검사 하나를 선택하며
두 검사를 몰래 실행하지 않습니다. 적용과 런타임 검사에는 지원되는 POSIX 연산이 필요합니다.
Windows에서는 이 워크플로를 안전하게 거부하며 기존 Windows `scan` 지원은 유지합니다.

## 별도 결정과 보존된 근거

실제 명령은 `share <request_id>`, 이후 `apply <proposal_id>`를 요구합니다. 새 비공개 복사본에만
적용한 뒤 정확한 소스, 파일 식별값, 제안, 검사 코드·digest, 예상 검사와 제한을 포함한 런타임
계획을 표시합니다. `verify <plan_id>`만 해당 계획을 승인합니다. Enter는 거절, `cancel`은 취소입니다.
선택 옵션, 로그인, 적용 승인은 런타임 실행 승인이 아닙니다.

최신 결정은 메모리에만 있고 300초 이내 만료되며 최대 한 번 소비합니다. 계획·소스 변경, 만료,
기록 불가, 파일 상태 충돌 시 실행을 거부합니다. 실행 의도 기록 후와 worker 완료 후 소스를
다시 확인합니다. 검사 실패가 자동 복구를 뜻하지는 않습니다. 안전할 때 별도
`restore <proposal_id>` 선택을 제공하며 감지한 후속 변경을 덮어쓰지 않습니다.
보존된 복사본·스냅샷·`record.json`을 확인하세요.

런타임 기록은 journal schema `1.2`를 사용합니다(별도 scan report schema와 다름).
`verification_scope: owned-fixture-runtime`, `verification_status`, `runtime_verification_status`,
검사한 소스·검사·worker digest, 소요 시간, 종료 코드와 런타임 관찰을 기록합니다.
Python/FastAPI/Starlette/Pydantic의 관찰 버전은 메타데이터이며 바이너리 신뢰성 인증이 아닙니다.
소스 설정 세션은 journal schema `1.1`과 런타임 상태 `not-run`을 유지합니다.

AFTER 검사가 성공하면 `passed` / `runtime-check-passed`입니다. BEFORE는 health 응답이
정상이어도 `failed` / `debug-enabled`입니다. 의존성 누락·거절·만료는 `not-run`이며 timeout,
잘못된 worker 출력, 후속 수정이나 결과 기록 불확실성을 `passed`로 표시하지 않습니다.
외곽 중단으로 상태를 모르면 상태 필드를 생략할 수 있으므로 미실행으로 추측하지 말고 보존된
기록을 확인하세요. 승인 후 BEFORE로 복구해도 결과는 해당 AFTER digest를 검사한 과거 근거입니다.

## 프로세스 경계와 한계

고정 worker는 stdin으로 제한된 소스 바이트를 받으며 비공개 작업 디렉터리, 축소 환경,
최대 입력 1,024바이트·출력 4,096바이트, 시작·I/O 5초 제한과 별도 프로세스 그룹 종료·회수
1초 제한을 사용합니다. 시도는 한 번이고 재시도나 shell이 없습니다. 원시 stderr나 예외 상세를
진단 근거로 출력하지 않습니다.

ASGI 메시지는 메모리 안에서 교환하며 TCP/UDP listener나 HTTP client를 사용하지 않습니다.
이벤트 루프 내부 IPC와 프레임워크 스레드는 생성될 수 있습니다. 이는 **OS/네트워크 sandbox가
아닙니다**. Python 소스 모드는 `-I`를 쓰되 `-S`는 사용하지 않아 신뢰하는 인터프리터의 site
시작 hook과 설치 의존성이 실행될 수 있습니다. Frozen 모드는 번들 의존성을 사용하며 동일
실행 파일 자식에 대해 검증한 기존 PyInstaller 부모 정보를 보존합니다. 이는 일관성 검사이지
실행 파일 인증이 아닙니다. 신뢰하지 않는 인터프리터·실행 파일·의존성 환경에서 사용하지 마세요.

승인 기록은 사람의 신원 인증, 재시작/이어하기 증서나 적대적인 동시 쓰기 방어가 아닙니다.
임의 소스, 범용 runner, 생성 테스트, 자동 설치, 네트워크 스캔이나 악용 흐름은 지원하지 않습니다.

## 패키징 검사

릴리스 빌드와 새 다운로드 artifact 검사 작업은 기존 scan smoke에 더해 별도의 고정 런타임
smoke를 실행합니다. 내부 `_runtime-smoke` 진단은 대상 경로나 명령을 받지 않고 실제 패키지의
부모 프로세스에서 동일 실행 파일 worker를 시작해 내장 AFTER 예제를 검사합니다. 패키징
진단이며 사용자 결정 증서나 종단간 승인 검사를 대신하는 기능이 아닙니다.

일치하는 플랫폼의 외부 smoke 제한은 45초이고 worker 자체는 5초 및 별도 1초 제한을 유지합니다.
POSIX에서는 정확한 런타임 성공 근거를 요구하고 Windows에서는 worker를 실행하지 않은 명시적
지원 불가 결과를 요구합니다. 실제 Codex 계정은 사용하지 않습니다. 성공하더라도 깨끗한 소비자
환경 설치·업그레이드·서명/공증·실제 모델 연동·인가 보안을 보장하지 않습니다.
릴리스는 별도 [발행 절차](../releases/RELEASING.md)를 통과한 뒤에만 발행합니다.

요청·응답 검사는 공식 [ASGI HTTP 명세](https://asgi.readthedocs.io/en/latest/specs/www.html)를 따릅니다.

## 제한적 실제 검증 — 2026-09-12

런타임 커밋 `ce2834c354f7c25d53e417382f41687296a508fc`에서 새로 승인받은 실제 소스 CLI
시도 1회가 종료 0으로 완료됐습니다. Codex 초안 → 정확한 diff 복사본 적용 → 별도 승인한
런타임 검사 → 별도 승인한 복구를 수행했습니다. main/worktree의 원본 fixture와 복구된
복사본 해시는 모두 `c10770594e77cd1c1ec93c19ef2b810aea34ed873d8dbf392b57e50a1c2729df`였습니다.
검사한 AFTER 해시는 `e010818e7259ad5c1ebfc5dfcb6dc046100376c778a70d0657d7ebb1ed7fdcfe`입니다.

- 기존 Codex 관리형 ChatGPT 로그인, Codex 0.153.0, 협상된 모델 `gpt-6-astra`, 애플리케이션
  시도 1회·120초 제한·애플리케이션 재시도/대체 없음. 제공자 보고 사용량은 입력 5,573 /
  출력 376토큰, 초안 지연 15,309.473ms, 관찰된 경고/재시도 알림은 1/0개입니다.
- 런타임은 `passed` / `runtime-check-passed`, 287.004ms, 종료 0, `debug: false`, health 200 및
  `{"status":"ok"}`입니다. 관찰 버전은 Python 3.12.7, FastAPI 0.141.1, Starlette 1.6.0, Pydantic 2.13.5입니다.
- 계획은 `verification-1e279e9af021e553552ec084c81a529f3e808abb52a91226bc0fe5741f95eb2f`,
  worker는 `05ef28b904eadf28ffe149e0b0d045e3b2d58086edfe0a7139c417265719f2a7`입니다.
  보존된 journal schema 1.2에 검증 결정 소비와 복구 상태를 기록했습니다.

assistant가 사용자의 제한적 승인 아래 정확한 문구를 검토·입력했으며 독립적인 사람 검토
인증은 아닙니다. 해당 승인은 모두 사용했습니다. 보고된 토큰과 관찰된 복구 알림 0개는 과금/
제공자 시도의 강제 상한이나 실제 응답 모델 인증이 아닙니다. 정상 fixture 하나의 결과이며
일반 저장소·인가·보안 수정의 완료 조건이 아닙니다. 로컬 테스트와 native 가짜 transport
근거는 이번 실제 호출과 구분합니다.

같은 런타임 커밋에서 **Python 테스트 1,548개**가 168.73초에 통과했으며 Ruff, frontend
lint/format/build와 영한 문서 검사도 통과했습니다. 최초 제한 환경에서는 기존 자식 프로세스
정리 검사 5개가 `ps`를 실행하지 못했으며 테스트를 변경하지 않고 로컬 프로세스 조회 권한으로
재검사해 통과했습니다.

macOS ARM64 개발 바이너리 SHA-256은
`0b6ef1b4ddf541a74a0b18b2fde61b1867c9f03bc5d1274af27a59e6d96a5183`입니다.
선택/이동 바이너리 scan smoke 14/14와 고정 런타임 smoke 2/2가 통과했습니다. 별도의 native
실제 CLI → 로컬 fake Codex → 동일 native 런타임 worker → 복구 흐름도 정확한 결정 네 번,
외부 시작 15.593초, worker 1,708.617ms로 성공했습니다. 이 native 검사는 실제 제공자를 호출하지
않았으며 가짜 모델/사용량은 작성한 테스트 데이터입니다. 원본 해시를 유지하고 복구 후에도
검사한 AFTER digest의 과거 성공 결과를 journal 1.2에 보존했습니다. PyInstaller 내부 세마포어에
필요한 권한 때문에 제한적인 도구 sandbox 밖에서 실행했으며 제한 시간이나 성공 조건을 낮추지
않았습니다. 세 플랫폼 릴리스/다운로드 검증은 별도 완료 기준입니다.
