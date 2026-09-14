<p align="center">
  <a href="../../../reference/threat-model.md">English</a> ·
  <strong>한국어</strong>
</p>

# AuthZest 위협 모델

[문서 목차](../INDEX.md) · [보안 정책](../SECURITY.md) ·
[Codex fixture](../guides/CODEX_FIXTURE.md) · [런타임 검증](../guides/RUNTIME_VERIFICATION.md)

## 1. 개요

2026-09-14에 casing1/authzest의 소스 리비전
2521ca5f23030561e2b2117900943557db6a6706을 기준으로 검토했습니다. 아래 소스 위치는 이 기준을 가리킵니다.
이 문서는 아키텍처 근거가 있는 검토 지침이며, 완료된 보안 감사·취약점 목록·수정 효과의 증명이 아닙니다.
분석 대상 FastAPI 애플리케이션의 접근통제 정책이 아니라 AuthZest 자체를 모델링합니다.
별도의 오프라인 아키텍처 검토로 기준 소스를 대조했으며, 이는 감사 범위를 충족했다는 뜻이 아닙니다.

지원하는 제품은 한 운영자가 로컬에서 사용하는 CLI 중심 소스 분석기입니다. 일반 스캔은 대상 코드를
import하거나 모델을 호출하지 않고 정적 근거를 수집합니다. 선택적인 API/대시보드는 서버 시작 시 지정한
작업공간을 분석합니다. 별도의 POSIX Codex 흐름은 승인 후 번들 fixture 하나를 공유하고 정확한 debug
설정 변경만 허용하며, 복사본 적용·검증·복구를 각각 결정하도록 합니다. 해당 흐름은 일반 저장소 AI,
생성된 회귀 테스트 실행, 기존 checkout 수정을 지원하지 않습니다.

### 구성요소와 확인한 소스

| 구성요소            | 역할과 근거                                                                                                                                                                                                                                                                                                              |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 정적 core           | 소스 탐색과 리포트: [src/authzest/analyzer/repository.py:28](../../../../src/authzest/analyzer/repository.py#L28); 저장소 내부 AST 읽기: [src/authzest/parser/repository.py:20](../../../../src/authzest/parser/repository.py#L20).                                                                                      |
| CLI와 로컬 API      | 사용자가 선택하는 스캔 입력: [src/authzest/cli.py:43](../../../../src/authzest/cli.py#L43); 시작 시 경계를 고정하는 API: [src/authzest/api/app.py:27](../../../../src/authzest/api/app.py#L27).                                                                                                                          |
| 선택적 검토 계약    | 호출자 소유 승인과 기본 비활성 adapter: [src/authzest/runner/review.py:30](../../../../src/authzest/runner/review.py#L30); 이 helper는 사람을 인증하지 않습니다.                                                                                                                                                         |
| 실제 fixture 조정자 | 공유와 분리된 결정: [src/authzest/runner/codex_fixture.py:98](../../../../src/authzest/runner/codex_fixture.py#L98); 정확한 출력 검증: [src/authzest/codex/fixture_draft.py:185](../../../../src/authzest/codex/fixture_draft.py#L185).                                                                                  |
| Codex adapter       | 한 번 사용하는 버전 고정 외부 전송 계층: [src/authzest/codex/app_server.py:535](../../../../src/authzest/codex/app_server.py#L535).                                                                                                                                                                                      |
| 파일 적용           | 프로세스 내부 세션 상태: [src/authzest/runner/fixture_apply.py:44](../../../../src/authzest/runner/fixture_apply.py#L44); 비공개 복사본 연산: [src/authzest/runner/_fixture_workspace.py:49](../../../../src/authzest/runner/_fixture_workspace.py#L49).                                                                 |
| 검증과 발행         | 고정 worker: [src/authzest/runner/fixture_check.py:158](../../../../src/authzest/runner/fixture_check.py#L158), [src/authzest/runner/fixture_runtime.py:120](../../../../src/authzest/runner/fixture_runtime.py#L120); 조건부 발행: [.github/workflows/release.yml:132](../../../../.github/workflows/release.yml#L132). |

### 실제 자원과 권한

아래 경로는 코드에서 도출한 위치이며 사용자 인증정보나 실제 임시 디렉터리를 조사한 값이 아닙니다.
별도 프로세스나 빈 작업 디렉터리 자체는 운영체제 수준의 격리를 보장하지 않습니다.
저장소 import 색인은 root와 root/src를 사용합니다([parser:66](../../../../src/authzest/parser/repository.py#L66)).
리포트는 절대 root와 원문 파싱 오류 문자열을 포함하므로 내보낸 리포트가 로컬 메타데이터를 드러낼 수
있습니다([models:186](../../../../src/authzest/models.py#L186)). 일반 wheel/pipx 설치는 대시보드를
번들하지 않으며 소스 상대 경로 fallback이 모든 설치에서 정적 파일의 존재를 보장하지 않습니다.
설정된 ChatGPT 백엔드는 https://chatgpt.com/backend-api이며 독립적으로 검증한 경로가 아닙니다.
초기화 시 Codex 0.153.0을 확인합니다. 프로토콜 제한은 JSON 메시지/행당 256 KiB,
전체 수신 데이터 2 MiB, 이벤트 4,096개이며 애플리케이션 timeout은 최대 120초입니다
([버전:31](../../../../src/authzest/codex/app_server.py#L31),
[초기화:372](../../../../src/authzest/codex/app_server.py#L372),
[프로토콜:298](../../../../src/authzest/codex/app_server.py#L298)).

| 배포 또는 흐름                 | 자원 또는 기능                      | 설정과 우선순위                                                                                  | 안전하게 표현한 실제 값 또는 위치                                                                                 | 읽기·쓰기 주체 또는 수신자                                                     | 적용하는 통제                                                                            | 근거 또는 미확인 사항                                                                                                                                                                                                                                                                                                 |
| ------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI 스캔                       | Python 소스 읽기                    | 명시적 경로를 확장하고 해석                                                                      | 선택한 root 아래의 일반 파일이며 심볼릭 링크가 아닌 Python 파일                                                   | 로컬 분석기와 리포트 수신자                                                    | 제외 디렉터리·로컬 소스 확인, AST 파싱만 사용                                            | [analyzer:28](../../../../src/authzest/analyzer/repository.py#L28), [parser:20](../../../../src/authzest/parser/repository.py#L20); 적대적인 동시 작성자를 막는 샌드박스가 아닙니다.                                                                                                                                  |
| CLI UI                         | 고정 작업공간 리포트의 HTTP 접근    | 명시적 workspace 또는 현재 디렉터리; CLI가 AUTHZEST_SCAN_ROOT를 덮어씀                           | 기본 리스너 127.0.0.1:8000; 시작 시 고정한 root                                                                   | 로컬 API에 도달하는 클라이언트                                                 | 요청이 새 파일시스템 대상을 선택할 수 없음                                               | [cli:234](../../../../src/authzest/cli.py#L234), [cli:258](../../../../src/authzest/cli.py#L258), [API:43](../../../../src/authzest/api/app.py#L43); 애플리케이션 인증/origin 검문은 없습니다.                                                                                                                        |
| 직접 실행한 ASGI 애플리케이션  | 같은 작업공간 스캔                  | create_app의 명시적 scan_root, AUTHZEST_SCAN_ROOT, 현재 디렉터리 순                              | create_app이 고정한 해석된 디렉터리; 리스너는 ASGI 실행 설정에 따름                                               | 접근 가능한 API 클라이언트                                                     | 같은 고정-root endpoint                                                                  | [API:22](../../../../src/authzest/api/app.py#L22); 다른 실행기에 CLI의 루프백 기본값이 적용된다고 가정하지 않습니다.                                                                                                                                                                                                  |
| 대시보드 정적 파일 / Vite 개발 | UI 제공과 로컬 API 프록시           | 명시적 frontend_dist, 없으면 frozen 번들 또는 소스 트리; 별도 Vite 설정                          | 명시적 디렉터리 또는 _MEIPASS/frontend/dist 또는 소스 frontend/dist; Vite 5173 포트에서 127.0.0.1:8000으로 프록시 | 브라우저와 로컬 백엔드                                                         | 프런트엔드는 스캔 경로를 보내지 않으며 API가 root 선택을 담당                            | [API:15](../../../../src/authzest/api/app.py#L15), [API:50](../../../../src/authzest/api/app.py#L50), [frontend:54](../../../../frontend/src/App.tsx#L54), [Vite:4](../../../../frontend/vite.config.ts#L4).                                                                                                          |
| 명시적 doctor 명령             | 신뢰하는 Codex 진단 실행            | PATH에서 Codex 탐색; 일반적인 상속 프로세스 환경                                                 | 설치된 실행 파일과 버전/로그인 메타데이터; 모델 turn이 아님                                                       | 로컬 Codex와 터미널/JSON 수신자                                                | 명령별 5초 timeout                                                                       | [diagnostics:42](../../../../src/authzest/diagnostics.py#L42), [diagnostics:73](../../../../src/authzest/diagnostics.py#L73); 성공 stdout을 표시하므로 반드시 비식별 처리됐다고 간주하여 공개하지 않습니다.                                                                                                           |
| 승인한 Codex fixture           | 소스 공유와 계정/모델 권한 사용     | 기존 HOME/CODEX_HOME 유지; adapter 설정 재정의와 두 차례 실제 설정 검사                          | 빈 authzest-codex-empty-* cwd; 기존 Codex 관리 계정 위치; 내장 OpenAI 제공자                                      | 신뢰하는 Codex 실행 파일과 OpenAI                                              | 정확한 요청의 공유 승인, ChatGPT 계정 확인, 도구/runtime root 없음, endpoint 재정의 거부 | [환경:128](../../../../src/authzest/codex/app_server.py#L128), [설정:94](../../../../src/authzest/codex/app_server.py#L94), [검사:393](../../../../src/authzest/codex/app_server.py#L393), [초안:570](../../../../src/authzest/codex/app_server.py#L570); 계정 저장소와 제공자 라우팅을 독립적으로 증명하지 않습니다. |
| Fixture 적용 / 복구            | 파일 하나 교체와 기록 보존          | 시스템 임시 위치의 새 비공개 디렉터리; 내부/테스트 호출자는 parent를 지정할 수 있지만 CLI는 불가 | authzest-fixture-*/main.py, before.txt, after.txt, record.json                                                    | 로컬 운영자와 신뢰하는 프로세스                                                | 디렉터리 0700, 파일 0600, no-follow와 단일 링크 검사, 소스/결정 재검사                   | [workspace:56](../../../../src/authzest/runner/_fixture_workspace.py#L56), [교체:160](../../../../src/authzest/runner/_fixture_workspace.py#L160), [복구:516](../../../../src/authzest/runner/fixture_apply.py#L516); 보존하며 자동 삭제하거나 재시작하지 않습니다.                                                   |
| 소스 모드 정적 검증            | 고정 AST worker                     | 현재 인터프리터와 -I -S                                                                          | 임시 authzest-configuration-check-* cwd; stdin 최대 1 KiB, stdout 최대 4 KiB                                      | 신뢰하는 표준 라이브러리 worker와 검증된 출력의 조정자                         | 정확한 fixture 허용 목록, 축소 환경, 시작/I/O 5초와 정리 1초                             | [정적 명령/환경:50](../../../../src/authzest/runner/fixture_check.py#L50), [정적 실행:158](../../../../src/authzest/runner/fixture_check.py#L158); 대상 import나 실행은 하지 않습니다.                                                                                                                                |
| 소스 모드 런타임 검증          | Opt-in 고정 런타임 worker           | 현재 인터프리터와 -I로 신뢰하는 site 시작 코드와 설치 의존성 허용                                | 임시 authzest-runtime-check-* cwd; stdin 최대 1 KiB, stdout 최대 4 KiB                                            | 번들 코드의 고정 probe와 설치된 FastAPI/Starlette/Pydantic; 조정자가 결과 검증 | 별도 계획 승인, 정확한 fixture 허용 목록, 축소 환경, 같은 5초/1초 제한                   | [런타임 명령:44](../../../../src/authzest/runner/fixture_runtime.py#L44), [런타임 허용 목록:148](../../../../src/authzest/runner/fixture_runtime.py#L148); OS/네트워크 샌드박스나 자동 의존성 설치는 없습니다.                                                                                                        |
| Frozen 검증                    | 번들 고정 worker 재실행             | sys.executable과 숨김 worker 명령; 검증한 기존 _PYI_* 값 3개 유지                                | 기존 실행 파일과 _MEIPASS 압축 해제 디렉터리; 같은 임시 cwd 규칙                                                  | 신뢰하는 바이너리·번들 의존성·worker                                           | archive 경로, 압축 해제 경로, parent level 검사; 같은 fixture/결정 검사                  | [정적 명령/환경:50](../../../../src/authzest/runner/fixture_check.py#L50), [런타임 명령:44](../../../../src/authzest/runner/fixture_runtime.py#L44); 일관성 확인은 바이너리 증명이 아닙니다.                                                                                                                          |
| CI / 릴리스                    | 검토한 빌드 입력 실행과 산출물 발행 | PR/push CI는 contents:read; v* 태그 또는 수동 릴리스 workflow                                    | 빌드 산출물; 선행 job 뒤 태그에서 발행 job만 contents:write 사용                                                  | CI runner, 의존성 레지스트리, action 제공자, GitHub 릴리스 사용자              | main/tag 검사와 validate/build/다운로드 산출물 검증 단계                                 | [CI:3](../../../../.github/workflows/ci.yml#L3), [release:35](../../../../.github/workflows/release.yml#L35), [publish:132](../../../../.github/workflows/release.yml#L132); 호스팅된 보호 설정은 조사하지 않았습니다.                                                                                                |

## 2. 위협 모델, 신뢰 경계와 가정

### 자산, 행위자와 목표

소스 기밀성, 무관한 파일과 사용자 편집, Codex 계정 권한과 사용량, 제안/결정의 무결성,
정직한 근거와 실패 기록, 로컬 가용성, 릴리스 무결성을 보호합니다.
root를 선택하거나 요청을 승인하는 운영자는 소스 작성자나 텍스트를 제공하는 모델과 다른 행위자입니다.

악의적인 소스 작성자는 운영자가 선택한 저장소의 파일·경로·선언·주석을, 신뢰하지 않는 모델 응답은
반환 텍스트를 통제할 수 있습니다. 이것만으로 승인 권한·파일 쓰기 권한·도구 기능을 얻지는 않습니다.
API 호출자는 서비스에 도달할 때만 스캔을 요청할 수 있습니다. PR 기여자는 코드/빌드 변경을 제안할 수
있지만 발행 권한을 자동으로 받지는 않습니다. 공격자가 이미 운영자 계정·인터프리터·신뢰하는 Codex
설치·릴리스 토큰을 통제한다고 가정하지 않습니다.

유지해야 할 불변 조건은 다음과 같습니다.

1. 기본 스캔은 소스 전용·오프라인을 유지합니다. 정적 선언, 유효한 JSON, 빈 리포트, 성공 종료,
   debug/health 검사는 인가 정확성을 증명하지 않습니다.
2. 공유·적용·검증·복구는 별도 결정입니다. 로그인, 모델 출력, 런타임 검증 선택 플래그, 제안 ID만으로
   다른 단계를 승인하지 않습니다.
3. 실제 CLI는 유지하는 소스와 정확한 debug 설정 변경만 허용합니다. 모델은 임의 소스 경로·명령·도구·
   출력 식별자·더 넓은 쓰기 대상을 선택할 수 없습니다.
4. 적용·검증 결정은 내용/계획 ID에 묶고 만료를 확인하며 현재 프로세스에서 소비합니다.
   쓰기와 실행 전 파일 상태를 다시 확인합니다. 복구는 감지한 사용자 중간 편집을 덮어쓰지 않아야 하며,
   실패하거나 확정하지 못한 쓰기/검사를 성공으로 표시하지 않아야 합니다.
5. 런타임 worker는 임의로 제공된 코드가 아니라 일치하는 번들 상수만 실행합니다.
   메모리 내 ASGI health 검사는 익스플로잇 테스트나 범용 runner가 아닙니다.
6. 릴리스 권한은 신뢰하지 않는 기여와 분리합니다. 문서는 소스 전송·코드 실행·산출물 발행·계정 설정
   변경을 허가하지 않습니다.

조정자 검사는 [codex_fixture:142](../../../../src/authzest/runner/codex_fixture.py#L142)와
[codex_fixture:208](../../../../src/authzest/runner/codex_fixture.py#L208),
결정/소스 검사는 [approval:94](../../../../src/authzest/runner/approval.py#L94),
[적용:474](../../../../src/authzest/runner/fixture_apply.py#L474),
[검증:311](../../../../src/authzest/runner/fixture_apply.py#L311)에 있습니다.
런타임 실행 경계는 [_runtime_worker:107](../../../../src/authzest/runner/_runtime_worker.py#L107)에 있습니다.

### 가정, 제외 범위와 미해결 질문

- CLI와 Python 라이브러리 호출자는 이미 로컬 사용자 권한으로 동작합니다. 정확한 터미널 문구와
  메모리 내 기록은 흐름 제어이며 인증된 사람의 승인 영수증이 아닙니다. 내부 worker와 숨김 패키징
  smoke도 같은 사용자가 직접 실행할 수 있으므로 표시 여부가 권한 통제는 아닙니다
  ([cli:202](../../../../src/authzest/cli.py#L202)). 적용 helper는 호출자 소유 fixture 텍스트를
  받을 수 있고, 번들 소스 허용 목록은 실제 CLI와 고정 검증 경로에서만 적용합니다.
- 운영체제, 인터프리터/site 시작 코드, 설치 또는 번들 의존성, Codex 실행 파일과 관리 계정 저장소를
  신뢰합니다. cwd가 비어 있어도 Codex는 HOME/CODEX_HOME을 상속합니다. 도구 금지/read-only 설정은
  모델 세션을 제한하며 신뢰하는 제공자 프로세스의 계정/네트워크 접근을 격리하지 않습니다.
  endpoint·실제 응답 모델·실행 파일·사람 신원의 독립적인 증명을 주장하지 않습니다.
- 복사본 흐름에서 같은 사용자 권한의 적대적인 동시 작성자를 제외합니다. 비공개 권한과 원자적 교체는
  이러한 행위자에 대한 compare-and-swap이 아닙니다. 로컬 소스 스캔도 불변 파일시스템 스냅샷이 아닙니다.
  적대적인 저장소를 무인 분석하기 전 전체 파일 수/바이트/시간 예산은 별도 검토가 필요합니다.
  Codex/worker 제한이 정적 스캔까지 제한하지는 않습니다.
- create_app의 API에는 인증, tenant 격리, 명시적인 origin/Host 보호가 없습니다.
  로컬에서 운영자가 통제하는 용도를 유지합니다. 공개/공유 배포는 지원하지 않습니다.
  브라우저에서 루프백으로 향하는 악용은 구체적으로 도달 가능한 요청/읽기 경로를 확인한 뒤 취약점으로
  판단해야 합니다.
- Windows 스캔과 POSIX fixture 적용/검증은 다릅니다. 정확한 설정/health 데모는 인증/소유권 PoC가
  아닙니다. 테스트 fixture에 의도적으로 안전하지 않은 설정이 있을 수 있으므로 존재만으로 문제를
  제기하거나 이를 소비하는 제품 코드를 검토에서 제외하지 않습니다.
- 갱신된 루트 [SECURITY.md](../../../../SECURITY.md#safe-use)은 구현된 opt-in fixture 전송을
  설명하며 기밀성/기본 비활성 요구사항을 유지합니다. 공개 번들 fixture는 일반 소스의 비밀정보
  탐지나 제거를 증명하지 않습니다.
- Adapter는 애플리케이션 시도 횟수·프로토콜 바이트/이벤트·시간을 제한하지만 모든 제공자 내부
  재시도나 금전 사용량을 제한하지 않습니다. 누락된 사용량은 미확인으로 유지합니다.
  Codex 호스팅 PR 리뷰는 이 adapter와 다른 서비스이며 이 문서에서 해당 설정·원격 보존·계정 상태를
  조사하거나 변경하지 않았습니다.
- [릴리스 범위](../releases/RELEASING.md)에 따르면 바이너리는 서명/notarization을 제공하지 않습니다.
  체크섬 일치는 함께 대체된 바이너리와 체크섬을 인증하지 않습니다. 호스팅된 tag/branch 보호와
  외부 승인은 미확인으로 남깁니다. main에 대한 수동 실행과 달리 태그를 대상으로 수동 실행한
  릴리스 workflow는 발행할 수 있습니다.

## 3. 공격 표면, 완화책과 공격자 시나리오

아래는 우선순위를 정한 검토 가설이며 검증된 취약점이 아닙니다. 우선순위는 조사 순서이지 발견한
취약점의 심각도가 아닙니다. 주장하는 권한 획득은 각각 소스 근거로 검증해야 합니다.

| 우선순위 | 시나리오와 얻는 권한                                                          | 전제조건                                                         | 영향                                          | 기존 통제                                                                        | 완화책                                                                                                   | 근거                                                                                                                                                                                                  |
| -------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | 소스 경로나 저장소 규모가 root 외부 읽기 또는 자원 고갈을 유발                | 운영자가 공격자 통제 소스를 선택; race에는 동시 작성자 필요      | 기밀성 또는 로컬 가용성                       | 로컬 일반 파일 검사와 AST 전용 import; 전체 스캔 예산은 확립되지 않음            | root를 좁게 유지하고 링크/race를 테스트하며 무인 확장 전 명시적 스캔 예산 추가                           | [parser:20](../../../../src/authzest/parser/repository.py#L20), [analyzer:28](../../../../src/authzest/analyzer/repository.py#L28)                                                                    |
| 1        | 모델 텍스트가 소스 공유 확대·도구 사용·임의 패치를 시도                       | 명시적으로 승인한 fixture turn과 신뢰하지 않는 응답              | 독립적인 검문 실패 시 미승인 공개·쓰기·실행   | 고정 요청과 정확한 변경, 엄격한 ID, 서버 요청 거부, 실제 도구/컨텍스트 검사      | 호스트 검증과 거부 테스트 유지; 프롬프트 지침을 유일한 통제로 삼지 않기                                  | [초안:185](../../../../src/authzest/codex/fixture_draft.py#L185), [프로토콜:298](../../../../src/authzest/codex/app_server.py#L298), [설정:393](../../../../src/authzest/codex/app_server.py#L393)    |
| 1        | 오래되거나 바뀐 제안/파일이 승인을 재사용하여 다른 상태를 덮어씀              | 승인 뒤 내용/계획 변경 또는 재사용 시도                          | 무결성과 복구 가능성                          | 결합된 결정, 만료, 단일 소비, 비공개 descriptor, 검사한 교체와 별도 복구         | 민감한 소비 지점에서 검사 유지, 변경 상태 거부, journal을 승인으로 재실행하지 않기                       | [승인:94](../../../../src/authzest/runner/approval.py#L94), [적용:474](../../../../src/authzest/runner/fixture_apply.py#L474), [교체:160](../../../../src/authzest/runner/_fixture_workspace.py#L160) |
| 1        | 검증이 생성된 명령/소스를 받거나 미실행 검사를 수정 성공으로 보고             | 새 runner/fixture 지원 또는 잘못된 worker 응답이 조정자에 도달   | 호스트 코드 실행 또는 잘못된 보안 확신        | 별도 계획 결정, 정확한 소스/worker ID, 고정 상수, 제한된 출력/상태 검증          | 검토한 허용 목록과 실패 테스트로 확장; 임의 실행 전 실제 격리 설계                                       | [검증:311](../../../../src/authzest/runner/fixture_apply.py#L311), [worker:107](../../../../src/authzest/runner/_runtime_worker.py#L107)                                                              |
| 2        | 접근 가능한 API가 작업공간 메타데이터를 노출하거나 비싼 스캔 반복을 허용      | 다른 행위자가 리스너에 도달하거나 브라우저-origin 공격 경로 성립 | 공개 또는 가용성; tenant 경계를 보장하지 않음 | CLI 루프백 기본값과 시작 시 고정 root; 호출자 경로 없음                          | 공개 바인딩 금지; 공유 배포 전 인증/origin/자원 통제 추가와 테스트                                       | [cli:234](../../../../src/authzest/cli.py#L234), [API:27](../../../../src/authzest/api/app.py#L27)                                                                                                    |
| 2        | 제공자 출력/진단 또는 보존 기록이 검토자를 오도하거나 공유 시 메타데이터 유출 | 운영자가 신뢰하지 않는 설명을 읽거나 로컬 출력을 공개            | 잘못된 결정 또는 정보 공개                    | 실제 흐름은 JSON 텍스트를 escape하고 전송 실패를 비식별 처리; 기록은 상태를 구별 | 설명을 신뢰하지 않고 내보내는 진단/기록 검토·비식별 처리; 실제 흐름의 출력 보장을 doctor에 적용하지 않기 | [출력:58](../../../../src/authzest/runner/codex_fixture.py#L58), [진단:99](../../../../src/authzest/diagnostics.py#L99), [세션:44](../../../../src/authzest/runner/fixture_apply.py#L44)              |
| 2        | 스트림/재시도 동작이 예상보다 많은 시간 또는 계정 사용량 소비                 | 운영자가 실제 요청을 승인                                        | 로컬 가용성과 사용량                          | 애플리케이션 turn 1개, deadline, 이벤트/바이트 상한, 프로세스 그룹 정리          | 미확인 사용량 명시, 실제 인수 검사는 별도 승인, 금액 상한을 보장한다고 표현하지 않기                     | [전송:535](../../../../src/authzest/codex/app_server.py#L535), [프로토콜:298](../../../../src/authzest/codex/app_server.py#L298), [정리:149](../../../../src/authzest/codex/app_server.py#L149)       |
| 2        | 신뢰하지 않는 기여/빌드 의존성이 릴리스 권한 경계를 넘거나 산출물 대체        | 구체적인 CI/의존성/검문 실패; 관리자 침해를 가정하지 않음        | 릴리스 사용자에 대한 공급망 영향              | 읽기 전용 CI 토큰, tag/main·산출물 검문, publish에 분리한 쓰기 권한              | 권한 있는 workflow 변경 검토, 의존성/빌드 출처와 다운로드 바이트 확인, 호스팅 규칙은 별도 재검사         | [CI:7](../../../../.github/workflows/ci.yml#L7), [release:35](../../../../.github/workflows/release.yml#L35), [publish:132](../../../../.github/workflows/release.yml#L132)                           |

## 4. 심각도 조정 (Critical, High, Medium, Low)

| 수준     | 조건부 예시                                                                                                     | 반례 / 필요한 근거                                                                                                                          |
| -------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Critical | 실제 경계 우회로 신뢰하는 배포 바이너리를 침해하여 다수 사용자에게 영향을 주거나 이에 준하는 광범위한 권한 실행 | 악의적인 PR 제안, 안전하지 않은 테스트 fixture, 이미 침해된 관리자 계정만으로 성립하지 않습니다. 발행/권한 경로를 증명해야 합니다.          |
| High     | 공격자가 통제하는 소스/모델 출력으로 미승인 민감 파일 접근·임의 코드 실행·승인 대상 외부 쓰기 획득              | 로컬 운영자가 승인한 행위와 정확히 제한한 debug 설정 변경은 무단 권한 획득이 아닙니다. 입력 통제·도달 가능성·실패한 검문을 확인해야 합니다. |
| Medium   | 도달 가능한 비신뢰 입력 경로로 의미 있지만 제한된 서비스 거부·한정된 공개·중요한 근거 훼손 발생                 | 미지원 공개 배포나 분석 불완전성만으로 증명되지 않습니다. 영향받는 데이터·노출·반복 가능성·실제 제한을 확인해야 합니다.                     |
| Low      | 좁은 영향과 제한적인 전제조건 아래 보안 관련 정보 노출 또는 무결성 약점                                         | 단순 외관 오류나 가상의 통제 실패가 자동으로 취약점이 되지는 않습니다. 실제 보호 자산과 얻는 권한을 설명해야 합니다.                        |

확신도와 영향을 분리하고, 미확인 전제조건을 심각도 상향으로 대체하지 않습니다.
소스 선택, adapter/도구 접근, 승인 ID, 파일 적용, worker 실행, API 노출, 릴리스 권한이 바뀌면
모델을 다시 검토하고 두 언어와 소스 위치를 함께 갱신합니다.
이 문서는 권한을 추가하거나 설정을 바꾸거나 보안 속성을 인증하지 않습니다.
