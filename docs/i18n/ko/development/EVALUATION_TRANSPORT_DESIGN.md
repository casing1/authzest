<p align="center">
  <a href="../../../development/EVALUATION_TRANSPORT_DESIGN.md">English</a> ·
  <strong>한국어</strong>
</p>

# 평가 invocation·직접 수신 경계 설계

[문서 목차](../INDEX.md) · [평가 프로토콜](EVALUATION_PROTOCOL.md) ·
[개발 계획](DEVELOPMENT_PLAN.md) · [이슈 #84](https://github.com/casing1/authzest/issues/84)

## 현재 순수 slot/batch 조합 — 2026-11-09 KST

`scripts/evaluation_coordinator.SlotCoordinator`는 기존 recipe/JSONL/preflight/session/turn 검사를
제공된 discovery 후 generation 순서로 조합하고 각 단계에 EOF·정상 종료·정리 확인을 요구합니다.
`scripts/evaluation_batch_coordinator.BatchCoordinator`는 원래 시계/예산을 초기화하지 않고 기존
dispatch ledger와 slot 상태를 연결합니다. `turn/start`에서만 모델 송신을 표시하며 정확한 RPC ack·
생명주기 확인 뒤 finish하고 첫 nonvalid에서 후속 슬롯을 멈추되 전체 예정 분모를 보존합니다.
[현재 제한과 순수/POSIX 테스트 명령](EVALUATION_PROTOCOL.md#순수-slotbatch-조합--실제-transport-아님)을 참고하세요.

호출자가 제공하는 바이트/종료/정리/시각 상태이지 I/O·launcher·실제 timer 강제·제공자 신원 인증·
실제 평가가 아닙니다. 프로세스 테스트에는 고정 소유 가짜 자식만 사용하며 선택 turn 부분집합은
더 넓은 유효 프로토콜 변형을 계속 거부하고 전체 recipe 검증이 아닙니다. 실제 생명주기/호환성 조건·
별도 실행 허가는 남아 있습니다. 제품/고정 버전/recipe/codec/preflight/JSONL/semantics/dispatch/
데이터/v1/수학/과거 자료·제품 `0.1.0a4` / 리포트 `1.2`는 그대로입니다. 신원 인증/새로움/준비/승인/
trial 수용/실제 동결은 false이며 #84는 체크 7개 미완료인 OPEN입니다. 실제 Codex/계정/모델/정책
worker/네트워크 호출·위험 수용·릴리스는 없습니다.

## 선택 합성 의미 검사 단계 기록 — 2026-11-08 KST

아래 단계는 위 순수 coordinator 조합 이전의 기록입니다. Coordinator 없음/다음 단계 표현은 당시
상태이며 개별 의미 validator는 계속 순수하고 변경하지 않았습니다.

순수 `evaluation_semantics`·`evaluation_session_semantics`·`evaluation_turn_semantics` 모듈은
제한된 detached 후보/선언 경계·선택한 session/목록/thread/settings 검사·기존 codec을 사용하는
연결된 합성 final-answer 순서 하나를 구분합니다. 미지원 변형은 이 좁은 정책의 범위 밖이지 반드시
프로토콜 무효는 아닙니다. 더 넓은 recipe 구현이나 JSONL/preflight/`Batch`의 coordinator 연결이
아닙니다. [현재 범위와 순수 테스트 명령 3개](EVALUATION_PROTOCOL.md#선택한-합성-응답-의미-검사--trial-아님)를 참고하세요.

[App Server 프로토콜 안내](https://learn.chatgpt.com/docs/app-server)는 선택 형식의 근거이지 런타임
증거가 아닙니다. 일치하는 ChatGPT 형태 계정/모델 목록 후보도
[신원·모델 사용 권한](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)을
입증하지 않습니다. 모든 기록은 호출자 제공이며 제공자/프로세스/I/O/CLI·인증된 새로움·실제 평가/
결과·trial 수용·준비 완료·실제 동결을 추가하지 않습니다. 다음은 coordinator 생명주기·미지원 recipe
경로이며 실제 실행에는 별도 승인이 필요합니다. 제품/고정 버전/recipe/codec/preflight/데이터/v1/수학/
과거 자료·제품 `0.1.0a4` / 리포트 `1.2`는 그대로이며 #84는 체크 7개 미완료인 OPEN입니다. 실제
호출·위험 수용·릴리스는 없습니다.

## 순수 JSONL·가짜 pipe 단계 기록 — 2026-11-08 KST

아래 단계는 위 별도 선택 의미 helper 이전의 기록입니다. Envelope 전용/의미 검증 대기 표현은 당시
상태이며 JSONL 모듈 자체는 여전히 envelope만 다룹니다.

`scripts/evaluation_jsonl.py`는 공유 예산을 제한하고 닫힌 envelope/연결을 검사하는 순수 점진적
바이트 framer·직렬 RPC inbox를 추가합니다. 허용 notification payload의 의미는 아직 미검증이며
framing/ack만으로 설정·목록·thread/turn 완료·평가 결과를 확인하지 않습니다. 비동기 제공자
transport·공개 launcher·CLI·로그 importer·`Batch`/preflight 연결이 아닙니다.

테스트만 고정 소유 Python 가짜 JSONL fixture를 빈 임시 cwd·최소 환경·제한된 테스트 대기/정리로
stdio 실행합니다. Codex/App Server·계정·모델·새 정책 worker를 실행하지 않으며 OS sandbox나 운영
timeout 강제를 입증하지 않습니다.
[순수/POSIX 가짜 pipe 테스트 명령과 제한](EVALUATION_PROTOCOL.md#순수-jsonlrpc-검사와-소유-가짜-pipe)을 참고하세요.
다음은 의미 수준 preflight/모델/목록/thread/turn 검증·coordinator 생명주기이며 실제 경로는 별도
승인이 필요합니다. 아래 시작 소스 검토는 런타임 관찰이 아닌 소스 감사로 유지합니다. 제품/고정 버전/
recipe/codec/preflight/ledger/v1/수학/데이터/과거 자료·제품 `0.1.0a4` / 리포트 `1.2`는 그대로입니다.
런타임/준비/승인/실제 동결 flag는 false이고 #84는 체크 7개 미완료인 OPEN이며 실제 AI 호출·위험
수용·릴리스는 없습니다.

## 오프라인 설정 preflight·시작 검토 기록 — 2026-11-08 KST

아래 단계는 위 순수 JSONL/가짜 pipe 후속 구현 전 기록입니다. 다음 단계 표현은 당시 상태이며
소스에서 도출한 시작 한계는 그대로 유효합니다.

`scripts/evaluation_preflight.py`는 제한된 호출자 제공 설정 후보를 검사하고 식별정보 없는 요약을
반환하는 순수 `check_config` / `compare_configs`를 추가합니다. 좁은 정책은 정확한 recipe 값·
알려진 비활성 생략/null·명시적 제한 MCP map·두 이름 집합의 일치를 요구하며 generation은 모든
서버에 `enabled=false`를 요구합니다. 알 수 없는 추가 값은 미지원이지 반드시 프로토콜 무효는
아닙니다. Origins/MCP 내용은 opaque JSON으로 전체 스키마/출처 검증이 아닙니다. CLI·RPC·프로세스·
timer·계정/모델 조회·worker·로그 import를 추가하지 않고 `Batch`에도 연결하지 않습니다. 기존
recipe descriptor/ID는 그대로입니다.
[API 한계와 합성 테스트 명령](EVALUATION_PROTOCOL.md#순수-오프라인-설정-preflight--시작-동작의-증거-아님)을 참고하세요.

기록한 생성 `ConfigReadResponse` SHA-256은
`96a04a3f7fff2dc7fafc9f831e8bcd422e021d697dd2c14c801f098a9f21396d`이며 문서 식별자이지 실행
파일/런타임 근거나 전체 스키마 검사기가 아닙니다.

읽기 전용 소스 검토는 Codex annotated tag `rust-v0.153.0`, tag 객체
`6bc50f104dcc0192e696cdeae721dfc19b507391`에서 가리키는 commit
`41e22fee981a63b3698df7ed36bad393cda24715`를 사용했습니다. 서명 없는 tag이며 실행 파일 증명이나
사용자 시작 동작의 관찰이 아닙니다. 소스에서 도출한 결론은 다음과 같습니다.

- [`config/read`](https://github.com/openai/codex/blob/41e22fee981a63b3698df7ed36bad393cda24715/codex-rs/app-server/src/config_manager_service.rs#L114-L174)는
  CLI 재정의를 적용하고 계층 config/requirements·일부 실제 feature 조정을 반환할 뿐 전체 런타임
  MCP 목록이나 증명은 아닙니다. cwd 생략 시 프로젝트 계층을 생략합니다.
  [재귀 설정 병합](https://github.com/openai/codex/blob/41e22fee981a63b3698df7ed36bad393cda24715/codex-rs/config/src/merge.rs#L95-L133) 때문에
  `mcp_servers={}`로 상속 항목을 지우지 못합니다.
- 유효 `plugins_enabled=false`이면
  [guard에 따라 plugin warmup을 건너뜁니다](https://github.com/openai/codex/blob/41e22fee981a63b3698df7ed36bad393cda24715/codex-rs/core-plugins/src/manager.rs#L2735-L2859).
  하지만 시작 효과가 전혀 없다는 뜻은 아닙니다.
  [시작 processor](https://github.com/openai/codex/blob/41e22fee981a63b3698df7ed36bad393cda24715/codex-rs/app-server/src/message_processor.rs#L316-L375)는
  [online 모델 갱신 경로](https://github.com/openai/codex/blob/41e22fee981a63b3698df7ed36bad393cda24715/codex-rs/app-server/src/models_refresh_worker.rs#L38-L64)가
  있는 worker를 시작합니다. 실제 네트워크 요청이 발생했다는 증거는 아닙니다.
- 검토한 initialize/config-read 경로는 MCP 연결을 만들지 않지만 threadless
  [`mcpServerStatus/list`는 eager connection set을 생성합니다](https://github.com/openai/codex/blob/41e22fee981a63b3698df7ed36bad393cda24715/codex-rs/codex-mcp/src/mcp/mod.rs#L468-L526).
  이를 수동적 preflight로 추가하지 않습니다. Manager 생성 자체와 연결 생성은 다릅니다.

이는 호환성/시작 검토 조건이지 제품 취약점 판정이나 실제 격리 증거가 아닙니다. 유효 설정 읽기를
설명하는 [App Server 안내](https://learn.chatgpt.com/docs/app-server)와
[MCP `enabled=false` 옵션](https://learn.chatgpt.com/docs/config-file/config-reference)도 초기화 전
동작을 증명하지 않습니다. 다음은 이 시작 경계를 명시한 별도 가짜 JSONL/파서/생명주기 단계이지 실제
transport 준비 완료가 아닙니다. 런타임/준비/실행/실제 동결 flag는 false이며 제품 `0.1.0a4` / 리포트
`1.2`·고정 버전·v1/수학/과거 자료·#84 미완료 체크 7개는 그대로입니다. 실제 AI/worker 호출·위험
수용·릴리스는 없습니다.

## 오프라인 dispatch 후속 구현 기록 — 2026-11-08 KST

아래 단계는 위 설정 검사기/소스 검토 이전의 기록이며 검토 대기 표현은 당시 상태입니다. 과거
recipe/설계 주장을 현재 런타임 근거로 승격하지 않습니다.

`scripts/evaluation_dispatch_recipe.py`는 직접 관리하는 descriptor/recipe ID와 해시·바이트 제한이
있는 canonical JSONL 프레임 후보를 구체화합니다. 요청 모델/effort·공통 codec 지시를 명시하며
가변 제품 설정을 import하거나 변경하지 않습니다. 생성 실험 스키마의 직접 관리하는 일부
projection은 요청 형식만 검사하며 전체 묶음·중첩 스키마 제공자 지원·유효 설정·도구 격리를
확인하지 않습니다. `remoteControl/status/read`는 `params=null`을, `initialized`는 params 생략을
사용하며 아래에 정정 날짜를 기록합니다.

`scripts/evaluation_dispatch.py`는 새 preview namespace·과거 전이를 거부하는 revision ticket·
명시적 decide/reserve/send/ack/checkpoint/finish 상태를 갖는 순수 직렬 `Batch` 시뮬레이션입니다.
호출자가 제공하는 정수 나노초 `Clock`으로 확인 TTL 300초·수용 시 고정하는 `W`·원래 기준점 차이
5초·초기화하지 않는 슬롯 예산을 모형화합니다. 합성 null 답은 유효하며 첫 nonvalid나 미확인 정리에서
후속 슬롯을 중단하고 모든 예정 분모를 보존합니다. 결정·ack·정리는 호출자 주장이지 인증된 승인·
프로세스 검사·런타임 근거가 아닙니다.
[현재 API/CLI 경계](EVALUATION_PROTOCOL.md#오프라인-dispatch-recipe와-상태-시뮬레이션)를 참고하세요.

계정/설정 RPC·제공자/프로세스 실행·timer/취소/정리 강제·로그 import·영속적 프로세스 간 ledger·
채점은 미구현입니다. 다음은 유효 설정/discovery 시작 의미 검토, 이후 별도 가짜 프로세스 transport
경계입니다. 실제 수신/generation에는 새 소스/계정/모델/turn/시간 승인과 누락한 검토/동결 근거가
필요합니다. 기존 codec/고정 버전/제품 `0.1.0a4` / 리포트 `1.2`/v1/수학/과거 자료는 그대로이며
#84는 체크 7개 미완료인 OPEN·실제 동결 false를 유지합니다. 실제 AI/worker 호출·위험 수용·릴리스는 없습니다.

## 순수 codec 단계 기록 — 2026-11-07 KST

시간 순서를 보존한 이전 기록입니다. 아래 다음 단계 표현은 위 오프라인 dispatch 후속 구현 전
상태이며 현재 recipe/상태 helper가 없다는 뜻이 아닙니다.

`scripts/evaluation_invocation.py`는 직접 관리하는 오프라인 후보 factory·엄격한 외부 `0.2`/기존
내부 `0.1` decoder·미리보기·합성 dry-run만 제공합니다. 명령은
[현재 프로토콜](EVALUATION_PROTOCOL.md#오프라인-invocation-codec-후속-구현)을 참고하세요.
원래/최종 메시지 해시·스키마 해시를 구분하고 제한된 UTF-8 원문은 반환값 메모리에 보존하며
canonical 내부 JSON을 원문으로 표시하지 않습니다. 출력 스키마는 shaping 부분집합이고 strict
decoder가 검증의 기준이며 고정 App Server 지원도 미확인입니다. 이전 내부 답에 현재 ID를 감싸도
통과할 수 있으므로 검증 응답의 출처는 호출자 제공/미확인·`runtime_observed=false`이고 신원 인증/제공자 응답
새로움이 아닙니다.

계정/네트워크/프로세스/정답/채점/로그-import 접근·실제 AI/worker 호출은 추가하지 않습니다. 실제
capture/격리/실패 처리는 여전히 제안입니다. 아래 버전별 dispatch 제안 다음은 순수 오프라인 결정/
상태 테스트와 별도 가짜 프로세스 테스트입니다. 제품 adapter/고정 `0.153.0`·v1/수학/과거 자료·제품 `0.1.0a4` /
리포트 스키마 `1.2`·실제 동결 false·#84 미완료 체크 7개는 그대로이며 새 위험 수용·릴리스도 없습니다.
Codec 전달은 실제 실행/동결 승인이 아닙니다.

## 버전별 dispatch 제안 — 2026-11-08 KST

과거 설계 전용 단계 기록입니다. 아래 미구현/다음 단계 표현은 당시 제안이며 현재 오프라인 builder/
ledger가 없다는 뜻이 아닙니다. Params 정정 날짜는 본문에 표시하고 실제 프로세스/설정/수신 의미는
여전히 미구현으로 둡니다.

**설계만 추가하며 기준 main은 `851d84cd4ab35bb35d262e2dbef23af7810dc5f3`입니다.** 제안 recipe 이름은
`evaluation-stdio-0.153.0-v1`입니다. 이번 갱신은 dispatch API·결정 ledger·프레임 builder·프로세스
transport·실제 설정 동결을 구현하지 않습니다. 다음은 순수 오프라인 recipe/프레임·batch 상태
테스트이고 프로세스 생명주기 테스트는 해당 경계를 검토한 뒤입니다. 텀프 기능 확장이나 제품
비공개 `_turn` 재사용 허가가 아닙니다.

### 고정 버전 스키마 근거와 런타임 근거의 구분

설치 CLI가 보고한 버전은 `0.153.0`입니다. 로컬 `app-server generate-json-schema` 하위 명령으로
기본·`--experimental` 프로토콜 묶음을 생성했으며 서버 시작·계정/모델 RPC는 하지 않았습니다.
`experimentalApi=true`에서는 실험 스키마가 필드 기준입니다. 기본 묶음에는
`allowProviderModelFallback`·`environments`·`runtimeWorkspaceRoots` 등이 빠지므로 그 누락만 보고
미지원이라고 판정하지 않습니다.

해당 생성 결과 중 실험 스키마 원본 SHA-256은 아래와 같습니다. 공개 생성 프로토콜 문서의 식별자이지
실행 파일·서명 릴리스·실제 wire 수집·설정의 증거가 아닙니다. 생성 묶음을 저장소에 넣거나 현재
codec에서 import하지 않습니다.

| 생성 문서                                   | SHA-256                                                            |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `v2/ThreadStartParams.json`                 | `25f490368ec6df52a2a3b82a5469d2413307eb93439121b309f415b5648eee7a` |
| `v2/ThreadStartResponse.json`               | `a338467af5fc271ace917f9d1262405642c3df3b66116aa105343db86cc9a76d` |
| `v2/TurnStartParams.json`                   | `b36fb37326b1cf69f75c8b306f1f886d53a57c4b1b985e08e298e2407ea2ad02` |
| `v2/ThreadSettingsUpdatedNotification.json` | `f7865eabaa34c7895a1ae345e51c1ba181a63c649237d36583b80f9d759b0f53` |

[공식 App Server 문서](https://learn.chatgpt.com/docs/app-server)는 버전별 스키마 생성과 RPC 생명주기를
설명합니다. 이번에는 생성 파일을 읽고 로컬 제품 코드와 대조했으며 기존 가짜 fixture 전부를
기계 검증하지 않았습니다. 기존 fake Model/Thread/item/usage에는 생성 스키마의 필수 필드 일부가
없으므로 기존 테스트 통과가 전체 프로토콜 스키마 준수는 아닙니다. 프로토콜의 `outputSchema`는 임의
JSON을 받을 뿐 codec의 중첩 shaping 스키마를 제공자가 지원한다는 증거가 아닙니다. Config도 추가
키를 허용하므로 필드 존재만으로 실제 설정·기능 비활성화를 확인할 수 없습니다.

### 제안 recipe와 wire 선택

후속 소스 checkout 전용 POSIX transport는 가변 제품 설정을 import하지 않고 자체 recipe 값을
소유해야 합니다. 위 기준점 제품 소스의 정확한 `CONFIG`·`DISABLED_FEATURES` 값을 시작 descriptor로
삼되 fixture 전용 developer 지시는 codec의 정확한 공통 `INSTRUCTIONS`로 교체하고 모델·요청 effort·
`approvals_reviewer="user"`를 명시합니다. 두 모드의 thread base/developer 지시와 collaboration
developer 지시에는 같은 공통 지시 바이트를 사용합니다. 다음 오프라인 builder가 전체 값·선택 스키마·
제한·시계/실패 규칙을 구체화하고 해시해야 하며 이 문서는 실행 가능한 recipe 해시가 아닙니다.
알 수 없는 instruction/profile/provider/context 재정의를 조용히 상속하지 않습니다. Discovery 중
ambient MCP 동작을 포함한 유효 설정은 프로세스 구현 전 검토 조건이지 이 descriptor의 보장이 아닙니다.

| 단계               | 제안하는 정확한 선택과 필요한 관찰                                                                                                                                                  |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 프로세스 경계      | 슬롯당 순차 프로세스 그룹 최대 2개: config 전용 discovery 후 generation. 새 빈 cwd·stdio JSONL·실행 파일/initialize user agent 버전 `0.153.0`. Shell launcher 없음.                 |
| 초기화/설정        | `experimentalApi=true` 후 `initialized`, `includeLayers=false`의 `config/read`. 제한된 MCP 이름 최대 64개를 열거해 generation 재시작에서 각각 끄고 전체 recipe 값을 검증.           |
| 환경               | `PATH`·`HOME`·`CODEX_HOME`·`TMPDIR`·`LANG`·`LC_ALL`·`USER`·`LOGNAME`만 상속 가능. 기존 인증 위치를 보존하고 자격증명 복사·API key/proxy/endpoint 재정의 전달 금지.                  |
| 계정/목록          | 기존 ChatGPT 로그인만 허용, `refreshToken=false`의 `account/read`. `model/list`는 `limit=100`·`includeHidden=false`, 최대 10페이지/1,000개·중복 없는 진행 cursor.                   |
| 모델/effort        | 요청 모델과 일치하는 표시 항목 정확히 1개·명시 effort와 일치하는 `supportedReasoningEfforts[].reasoningEffort` 정확히 1개. 기본값·대체·alias·fallback 없음.                         |
| `thread/start`     | 정확한 모델/provider `openai`·`allowProviderModelFallback=false`·`ephemeral=true`, 빈 environments/tools/capability/workspace roots·read-only/on-request·reviewer `user`·고정 지시. |
| 초기 effort 설정   | 프로세스 config와 `thread/start.config`의 `model_reasoning_effort`를 요청값으로 설정. 응답의 non-null `reasoningEffort` 일치가 필수이며 누락은 미확인이지 성공이 아님.              |
| 초기 thread 근거   | 모델/provider/cwd/approval/reviewer/read-only no-network 일치·`thread.ephemeral=true`·빈 turns/지시 소스/roots·fork/parent context 없음. resume/fork/history import/steer 금지.     |
| `turn/start`       | 정확한 thread ID/모델/effort·`Invocation.message_text`와 같은 text 입력 1개·정확한 `Invocation.output_schema`·빈 environments/roots·동일 sandbox/approval/reviewer/cwd.             |
| Collaboration/tier | 명시적 `collaborationMode.mode="default"`·settings의 모델/`reasoning_effort`는 요청값·non-null 공통 `developer_instructions`, `serviceTierForTurn="default"`.                       |

**2026-11-08 스키마 정정:** 생성 실험 `ClientRequest`에서 `remoteControl/status/read` params는
선택적/null이며 `{}`가 아닙니다. 오프라인 프레임 후보는 `null`을 선택합니다. 일부 형식 대조일 뿐
제품 adapter 변경이나 런타임/제공자 호환성 결과가 아닙니다.

계정/목록/thread 생성 전에 `null`로 `remoteControl/status/read`를 호출하고 `status="disabled"`를
요구합니다. 누락·잘못된 형식·다른 상태면 batch를 거부하며 notification 부재를 비활성화의 근거로
삼지 않습니다. `collaborationMode`가 최상위 모델/effort/developer 설정보다 우선하고 null developer
지시는 mode의 내장 지시를 선택하므로 위의 명시적 일치/non-null 설정으로 조용한 대체를 막습니다.

생성 `ReasoningEffort`는 nonempty string이지 제품 어댑터의 5개 호환 값 목록이 아닙니다. 제한된 모델
목록의 지원값과 정확한 요청 label을 대조하고 default를 선택하지 않습니다. null/중복 모델 항목·cursor
순환·페이지 초과·잘못된 설정·필수 보고 effort 누락은 batch를 거부합니다. 서버 보고 설정도 숨은
제공자 연산의 telemetry는 아닙니다. 계정 식별자·설정 경로·모델 목록을 공개 근거에 노출하지 않습니다.

제품 retry 정책 대신 닫힌 event 정책을 사용합니다. 예상 method는 `thread/started`·
`thread/status/changed`·`thread/settings/updated`·`turn/started`·`turn/completed`·`item/started`·
`item/completed`·`item/agentMessage/delta`·제품에 나열된 reasoning delta 3종·
`thread/tokenUsage/updated`·`account/rateLimits/updated`·`model/verification`·
`model/safetyBuffering/updated`·`turn/moderationMetadata` 및 disabled일 때만 허용하는
`remoteControl/status/changed`입니다. 모든 필드/payload는 고정 스키마·의미 검증이 필요하며 method
허용만으로 충분하지 않습니다. ack 전 notification은 제한 내 대기시킨 뒤 일치하는 RPC 응답 후
연결을 검증하고 다른/중복 RPC ID·다른 thread/turn ID를 거부합니다.

`willRetry=true`를 포함한 모든 `error`·`warning`·`configWarning`·`guardianWarning`·deprecation·
auth recovery·model reroute·도구/승인 요청·예상 밖 item/context/settings·알 수 없는 event는 batch
치명 오류입니다. 경고 문장을 설정/사용량/승인으로 읽지 않습니다. 비공개 warning/error 내용은
버리고 제한된 닫힌 진단만 남깁니다. effort/collaboration effort·모델·developer 지시·reviewer·경계
값이 null/다르면 거부하고 누락 메타데이터를 검증된 값으로 표시하지 않습니다. 제품의 retry 알림
3개 허용을 재사용하지 않습니다. 완전하고 일치하는 settings 관찰이 없으면 설정은 미확인으로 두고
최종 JSON·완료가 통과해도 검증된 런타임 관찰을 게시하지 않습니다. 이미 시작됐거나 숨은 Codex retry·사용량의 상한/부재는 여전히
보장하지 못합니다.

명시적 `phase="final_answer"`·고유 item ID·제한된 text를 가진 연결된 `item/completed` agent
message와 그 뒤 동일 turn의 성공 `turn/completed`·null error를 요구합니다. 이 recipe에서 알 수
없는 phase는 final이 아닙니다. delta나 turn snapshot만으로 최종 결과를 만들지 않습니다.
Snapshot에 이미 완료된 같은 item이 다시 있다면 내용도 같아야 하며 다른/충돌 final을 추가하면
안 됩니다. 이후 기존 strict codec을 호출하고 정리가 확인된 뒤에만 관찰 결과를 게시합니다.
미보고 사용량은 null이며 마지막 turn 사용량은 전체 청구액이 아닙니다.

기존 제안 제한을 유지합니다. 완전한 JSONL 프레임당 256 KiB, 슬롯의 두 프로세스를 합쳐 수신
stream 2 MiB·event 4,096개, 대기 notification 최대 128개, startup/preflight/generation을 합쳐
슬롯 예산 `T` 1–120초 한 번입니다. Discovery/event 뒤 `T`를 초기화하지 않습니다. 정리 대기는
`T` 이후에도 이어질 수 있으나 생성 프로세스 그룹당 최대 5초이며 blocking 파일시스템 작업·전체
wall time·토큰/비용 상한이 아닙니다. 메시지/스키마가 각각 codec 제한 이하여도 실제 인코딩한
요청 프레임은 별도의 프레임 제한을 만족해야 합니다.

### 전체 batch 결정과 고정 시계

후속 전체 검토 1회에 선택한 모든 메시지/스키마·순서·정확한 설정/recipe·소스/계정 범위·최대
`N`개 one-turn 시도·시간/사용량 한계를 포함합니다. 정상 슬롯마다 다시 확인을 요구하지 않습니다.
새 실제 소스/계정/모델/turn/시간 허가와 미확보 검토/동결 근거는 별도 선행 조건이며 문서/CI 승인이
그 허가는 아닙니다. 현재 내용 ID나 호출자 제공 결정은 사람의 신원을 인증하지 않습니다.

저장하는 시각·차이는 모두 정수 나노초이며 아래 초 값을 각각 `1_000_000_000`배 변환합니다.
특히 `dispatch_deadline_ns=m_accept_ns+W_seconds*1_000_000_000`이고 확인/불일치 한계는 각각
`300*1_000_000_000`·`5*1_000_000_000`입니다. 아래 식의 초는 읽기 쉬운 축약이지
`monotonic_ns()`에 변환 없이 더하는 산술이 아닙니다.

후속 단일 소유 coordinator의 제안 규칙은 다음과 같습니다.

1. 한 프로세스에서 preview 생성 `m0=monotonic_ns()`·wall-clock `w0`를 고정합니다.
   `0 <= m-m0 < 300초`일 때 일치하는 batch 결정 정확히 1개만 수용합니다. 거절·잘못된/오래된
   결정·만료는 최종 상태이며 prompt 자동 갱신·timestamp 교체·재시작·import·resume은 없습니다.
2. 수용 시 `dispatch_deadline=m_accept+W`를 딱 한 번 정하며 `W=60+N*(T+10)초`입니다. `N`은 성공
   수가 아닌 전체 14/28/42슬롯입니다. `T=120`에서 최대 구간은 1,880·3,700·5,520초입니다.
   `+10`은 두 그룹의 명목 정리 대기 여유이지 완료 보장이 아닙니다.
3. 원래 planner 순서·동시 슬롯 1개를 유지합니다. 예약 전·turn 쓰기 전 전체 후보/recipe를
   재검증하고 두 지점 모두 시간을 검사합니다. 프로세스 시작 전 예약으로 슬롯을 소비합니다.
   첫 write 가능 시점 직전 await 없이 `turn_send_state=attempted`로 바꾸며 불확실한 write/ack가
   슬롯을 다시 채우지 않습니다.
4. 새 예약/전송은 `m < dispatch_deadline`일 때만 가능합니다. 전송 전 만료면 해당 슬롯과 나머지
   미전송 슬롯을 `skipped-expired`로 두고 attempted-send 상태를 따로 기록합니다. 만료 전 이미
   보낸 슬롯은 원래 `T`/정리 제한으로 마무리해 결과를 보존하며 만료로 timer를 연장하거나 새
   turn을 시작하지 않습니다.
5. 각 checkpoint에서 monotonic 값은 감소하면 안 됩니다. **원래 preview 기준점**으로
   `abs((wall_now-w0)-(mono_now-m0)) > 5초`면 clock-integrity 실패입니다. 수용/슬롯마다 기준점을
   갱신하지 않습니다. 활성 슬롯을 취소·정리하고 미전송 슬롯은 별도의 시계 실패 사유로
   건너뜁니다. 수용/예약/pre-write·관찰되는 async 진행 중 검사하고 wall time으로 권한을 늘리지
   않습니다. 이는 관찰된 큰 시계/절전 불일치 일부를 찾는 것이지 모든 절전·실시간 초과 탐지가
   아니며 5초 이하 불일치는 허용합니다.
6. 활동·유효 응답·사용자 지연·일부 진행으로 어느 deadline도 늘리지 않습니다. Preview 메타데이터는
   후보·recipe·전체 제한/순서/실패 정책·새 namespace 하나에 연결해야 합니다. 불변 오프라인 상태
   snapshot만으로 one-use를 강제할 수 없습니다. 후속 coordinator가 메모리 ledger 하나를 직렬로
   소유하고 과거 snapshot 재사용을 거부해야 합니다. 이 소스 전용 설계는 영속 저장/import나
   적대적 프로세스 방어를 약속하지 않습니다.

### 최종 결과와 구현 선행 조건

**첫 nonvalid 관찰에서 중단**하도록 정합니다. missing·invalid·failed·interrupted·timeout 슬롯은
정리 성공 여부와 무관하게 후속 전송을 중단하고 나머지는 `skipped-stopped`로 보존합니다.
유효한 null/unknown 답은 유효 응답이므로 batch를 멈추지 않습니다. 무결성/시계 실패·미확인 정리는
별도 치명 사유이며 주 실패·정리 결과를 독립 기록합니다. 예약했지만 전송하지 않은 것은 완료된
제공자 시도가 아닙니다. 거절/만료/미전송 슬롯을 포함한 전체 분모와 사유를 유지합니다. 순서 의존적
중도 중단 batch로 모드 우열을 비교하거나 실패 슬롯을 새 시도로 대체하지 않습니다. 채점은 별도입니다.

다음 오프라인 테스트는 정확한 recipe/프레임 해시·생성 스키마 형식 fixture·모델 목록 페이지/명시
effort·300초 경계/최대 `W`·시계 후퇴/전진/절전 예·기준점 재설정 금지·예약/송신 만료 경합·옛
snapshot 재사용·전송한 슬롯의 만료·null 유효성·실패/정리/skipped 분모를 다룹니다. 시계/event는
합성으로 표시하고 런타임 출처/제공자 새로움/실행 승인 flag는 false를 유지합니다. 프로세스 코드
전에는 전체 유효 설정/MCP 시작 의미를 검토하고 스키마를 따르는 가짜 프로세스 payload를 고정해야
합니다. 실제 중첩 스키마/제공자 지원·유효 harness context는 미확인입니다. 현재 codec·제품 adapter·
v1 값/바이트·채점 수학/이력·릴리스 버전·#84 체크는 변경하지 않습니다.

## 원래 제안 — 보존한 이력

아래 원래 설계는 당시 소스/날짜로 보존합니다. Codec/API가 미구현이라는 표현은 당시 상태이지 위의
현재 오프라인 후속 구현을 뜻하지 않습니다. 실제 transport는 지금도 미구현이며 제안 전달을 실행
승인으로 해석하지 않습니다.

## 상태와 목적

**제안이며 미구현 — 2026-11-07 KST.** 기준 main은
`42e5db7104fd715af1edf1a5032b7761dc1747ca`입니다. 호출 가능한 API·CLI 명령·제공자 연동·계정 조회·
실제 시험·실행 권한·새 실제 설정 동결을 추가하지 않습니다. 문서 전달/리뷰는 모델 실행 승인이나
벤치마크 준비 완료의 증명이 아니며 #84 체크 7개도 모두 미완료입니다. 기존 v1 과제/정답·채점
수학/과거 기록·제품 코드/의존성/버전·응답 스키마 `0.1`은 그대로이고 위험 수용·패치·릴리스도 없습니다.

다음 구현은 먼저 **순수 오프라인 invocation codec**, 그 뒤 별도로 검토한 평가 전용 transport와
가짜 프로세스 생명주기 테스트 순서입니다. 실제 비교에는 새 명시적 소스/계정/모델/turn/시간 결정과
[프로토콜](EVALUATION_PROTOCOL.md)에 명시한 미확보 검토/동결 근거가 여전히 필요합니다.
텀프로젝트 범위를 새로 확장하자는 제안이 아닙니다.

## 구분해야 하는 세 가지 주장

| 계층                            | 확인할 수 있는 것                                                         | 확인할 수 없는 것                                          |
| ------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 기존 호스트 receipt `0.1`       | 호출자 제공 메타데이터와 예상 로컬 슬롯의 일치·batch 분모 보존            | 실제 모델 실행·제공자 출처/새로움·영속적 일회용 강제       |
| 제안 모델 노출 invocation `0.2` | 현재의 불투명 invocation ID를 엄격히 되돌려주고 내부 `0.1` 답이 유효함    | 이전 답 재포장 불가능·신원 인증·실제 제공자 연산·정답 여부 |
| 후속 런타임 직접 수신           | 신뢰한 설치 Codex/호스트 프로세스가 연결된 로컬 요청·stream·완료를 관찰함 | 암호학적 제공자 증명·숨은 harness 전체 context·답의 진실성 |

호출자가 제공한 JSON/로그 import를 런타임 관찰 근거로 승격하지 않습니다. Nonce echo만으로 신원
인증·동의·제공자 응답의 새로움을 증명하지 않습니다. 오프라인/가짜 프로세스 결과는
`provider_freshness_verified=false`이며 codec은 런타임 관찰 출처 flag를 설정할 수 없습니다.

## 제품 어댑터 경계 유지

[`CodexAppServerAdapter`](../../../../src/authzest/codex/app_server.py)는 `0.153.0`에 고정되어 있으며
검증된 공개 진입점에서 소유 fixture/owner-policy 요청만 허용합니다. 비공개 `_turn`은 fixture 전용
base/developer 지시를 사용하고 평가 후보의 명시적 effort가 아니라 모델 목록의
`defaultReasoningEffort`를 선택합니다. 따라서 **평가 transport 인터페이스가 아닙니다.**

평가 prompt/schema를 이 비공개 메서드에 주입하거나 요청 타입/허용 목록을 넓히거나 제품 지시·
effort 선택·버전 지원을 조용히 바꾸지 않습니다. 후속 소스 전용 평가 transport가 자체의 제한된 요청
타입과 생명주기를 소유해야 합니다. 저수준 코드 공유를 위한 추출도 별도 호환성 검토 대상이며
이번 설계가 이를 허가하지 않습니다.

현재 [공식 App Server 문서](https://learn.chatgpt.com/docs/app-server)는 RPC 요청/응답 ID·turn별
`outputSchema`·서로 다른 완료 상태를 설명합니다. 설계 참고이지 최신 필드 전부가 고정 버전
`0.153.0`에도 존재한다는 증거는 아닙니다. Transport 구현 전 해당 버전의 생성 스키마를 검토하고
정확한 wire 필드/설정·event 허용 목록·호환성 테스트를 고정해야 합니다. 새 예시를 그대로 옮기거나
제품 어댑터 버전을 올리지 않습니다.

## 제안 순수 invocation codec

아래 모듈명은 제공 중인 인터페이스가 아닙니다. `scripts/evaluation_invocation.py`는 직접 관리하는
과제 전용 planner와 현재 프로세스의 collection 세션으로 후보를 구성하도록 제안합니다. import한
계획·임의 prompt/schema 사전·임의 소스 경로·평가자 정답 자료를 입력으로 받지 않습니다.

패킷 선택 전에 설정·계획·패킷 집합·슬롯 소속·task/request/trial ID·원래 애플리케이션 메시지
SHA-256을 재구성/재검증합니다. 호출자 제공 해시만 보지 말고 실제 패킷을 예상 슬롯과 대조합니다.
기존 planner/collector 계약은 그대로 유지합니다.

제안하는 외부 객체의 필드는 정확히 다음과 같습니다.

| 객체 | 필드와 의미                                                                                                                                             |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 입력 | `schema_version="0.2"`, `kind="evaluation-invocation-input"`, 불투명 `invocation_id`, 공통 `instructions`, 변경 없는 완전한 `0.1` 입력 payload인 `task` |
| 응답 | `schema_version="0.2"`, `kind="evaluation-invocation-response"`, 현재의 정확한 `invocation_id`, 변경 없는 완전한 `0.1` 응답 객체인 `response`           |

공통 외부 지시는 포장 관계를 분명히 해야 합니다. 기존 과제 지시/답 계약은 **내부 `response`
객체**에 적용하고 외부 객체는 `invocation_id`를 그대로 되돌려줍니다. 소스/정책/근거는 데이터로
취급하고 제공된 과제만 사용하며 도구/실행을 요청하지 않고 설명 없는 완전한 JSON 객체 하나를
반환합니다. 최종 지시 바이트·출력 스키마는 후속 검토 후보이며 이 문서가 동결하지 않습니다.
스키마는 구문/ID를 제한할 뿐 정답 값이나 평가자 정답 메타데이터를 삽입하면 안 됩니다.

새 버전 recipe·내용 ID namespace를 사용합니다. 새 collection namespace·trial/설정 연결·recipe
해시로 불투명 invocation ID를 **먼저** 도출하고 메시지에 넣습니다. 그 다음 완성된 canonical
UTF-8 `0.2` 애플리케이션 메시지와 출력 스키마를 각각 해시합니다. 자기 해시가 들어간 메시지를
다시 해시하는 순환 의존을 만들지 않습니다. 기존 `0.1` 메시지 해시는 명확히 다른 필드로 남기며
최종 `0.2` 메시지 해시라고 표시하지 않습니다. 전체 후보를 기존 plan ID·새 recipe·최종 메시지/
스키마·요청 설정에 연결합니다. 기존 계획을 실제 동결 계획으로 재명명하거나 새 메시지 바이트에
이전 ID를 전용하지 않습니다.

선택한 불투명 invocation ID·공통 포장 지시·원래 과제만 모델에 노출합니다. 전체 계획·mode/case/
split label·정답/manifest 해시·예상값·근거 설명·검토자 자료·계정 자료·로컬 경로는 애플리케이션
메시지 밖에 둡니다. 두 모드는 포장·소스/정책/질문/답 형식·스키마 구조가 같고 기존 선언 근거와
필요한 불투명 연결값만 다릅니다. 이 식별자 차이를 무작위 배정이나 blinding이라고 부르지 않습니다.

### 엄격한 응답 검증

제안 외부 상한은 내부 객체를 포함한 전체 UTF-8 응답 텍스트 64 KiB·JSON 깊이 16입니다. 모든
계층의 중복 key·비유한/overflow 숫자·잘못된 타입/필드/버전·추가 설명/fence·다른 invocation ID·
외부 포장 없는 `0.1` 응답을 거부합니다. 정확한 외부 echo부터 검사한 뒤 factory 소유 명세로
내부 객체를 기존 엄격한 `0.1` decoder에 전달합니다. 실제 수신 텍스트는 별도로 보존합니다.
이미 검증한 내부 객체의 canonical 재직렬화는 원래 제공자 응답이 아니므로 그렇게 표시하면 안
됩니다. 복구·강제 변환·부분 점수·무효/누락을 유효한 unknown으로 바꾸는 동작은 없습니다.
`""`는 알려진 빈 sorted-CSV 집합이며 null만 unknown입니다.

다른 namespace/슬롯/반복의 이전 응답은 그대로 제출하면 실패해야 합니다. 반례도 명시적으로
검사합니다. 이전 내부 답을 현재의 유효한 `0.2` 객체로 다시 감싸면 통과할 수 있습니다. 이 한계를
기록하며 codec이 출력을 인증하거나 새 모델 호출 발생을 증명한다고 주장하지 않습니다.

## 후속 평가 전용 직접 수신

`scripts/evaluation_transport.py`는 제안한 별도 coordinator이며 구현된 실행기가 아닙니다.
직접 관리하는 현재 후보·새 한정 결정만 받고 전송 직전 전체 미리보기를 재구성·대조해야 합니다.
**최초 turn 전송 가능 시점 전**에 해당 슬롯의 시도 권한을 소비합니다. 쓰기 실패나 응답 수신
불확실성을 이유로 애플리케이션 수준 시도를 추가하지 않습니다.
후속 동의 UI는 선택한 batch의 모든 메시지·설정·시도 수·시간/사용량 한계를 하나의 완전한 한정
결정으로 제시해야 하며 정상 슬롯마다 사용자 확인을 다시 요구하지 않습니다. 슬롯별 일회용 상태는
내부 제약이지 추가 권한이 아닙니다. Batch 전송 유효 구간·만료 상한·단조 시계 규칙은 프로세스 경계
구현 전 transport recipe에서 고정/검사해야 합니다. 미리보기가 무기한 유효하다고 보거나 자동 갱신하지
않습니다. 슬롯마다 새 빈 ephemeral thread와
turn 하나를 사용하고 resume·fork·과거 기록 import·steer·모델 대체·AuthZest 재시도를 허용하지
않습니다. 메타데이터 조회는 별도로 정리하는 프로세스를 쓸 수 있지만 모델 turn은 만들면 안 됩니다.
슬롯별 생성 transport를 분리하고 다른 슬롯의 context를 재사용하지 않습니다. 슬롯당 OS 프로세스가
반드시 하나라는 뜻은 아닙니다.

생성 전에 정확한 후보 모델과 명시적 effort를 고정 버전 목록·서버가 보고한 설정과 대조합니다.
기본 effort나 대체 모델을 선택하지 않습니다. 고정 프로토콜이 필수 설정을 확인할 수 없으면
강제했다고 주장하지 말고 실제 벤치마크 시작을 거부합니다. 요청값과 서버 보고값은 별도로 남기며
서버 보고도 숨은 제공자 연산의 증명이 아닙니다. 선택적 사용량/시간 자료가 없으면 0이 아닌 null입니다.

고정 base/developer 지시·정제된 환경·빈 작업 디렉터리·상속 설정 검사·외부 context/탐색/도구/
MCP/apps/hooks 비활성화·sandbox 설정을 하나의 버전 있는 평가 recipe로 검토합니다. 예상하지 못한
도구/승인 요청·context/설정 변경·모델 reroute·다른 RPC/thread/turn ID·모호한 최종 출력을
거부합니다. 애플리케이션 메시지 해시는 전체 Codex wire 바이트나 숨은 harness 지시를 포함하지
않습니다. 빈/read-only 디렉터리만으로 전체 context 격리를 주장하지 않으며 명시적으로 구성한
Codex harness를 비교하는 것이지 bare 모델 비교가 아닙니다. 설치 Codex·관리하는 인증·안정적인
로컬 호스트는 신뢰 대상입니다.

런타임은 실제 전송 시도·일치하는 RPC 응답·thread/turn ID·완료된 최종 agent-message item 하나·
동일 프로세스의 성공한 `turn/completed`를 직접 연결해야 합니다. 부분 delta·최종 답처럼 보이는
JSON·성공한 완료 이전의 일치 echo만으로 시험 완료가 아닙니다. 단조 시계의 전송/완료 구간을 시작·
정리 시간과 분리해 기록하고 제공자 자체 지연이라고 부르지 않습니다. 검증에 필요한 제한된 비공개/
비식별 근거만 남기며 인증정보·원시 stderr·계정 프로필은 보존하지 않습니다. 공개 요약은 별도 범위
확인이 필요하며 이번 설계가 원본 로그 공개나 새 영속 export/import 기능을 승인하지 않습니다.

후속 transport의 제안 상한은 명시적 후보 시작/생성 adapter 예산 1–120초·생성한 프로세스 그룹마다
별도 정리 대기 최대 5초(슬롯 전체의 정리 합계 5초 상한은 아님)·JSONL frame당 256 KiB·stream 합계
2 MiB·event 4,096개·대기 알림 128개입니다.
상한을 넘으면 슬롯 실패 후 정리합니다. 애플리케이션 상한이지 OS sandbox·전체 파일시스템 시간 상한·
토큰/크레딧 상한이 아닙니다. 이 설계로 Codex 내부 재시도/사용량 상한을 보장할 수 없습니다.
노출된 retry/recovery 오류는 시험을 조용히 재시작/복구하지 말고 거부하되 숨은 재시도를 막았다고
주장하지 않습니다. 실제 실행 동의에도 이 한계를 알려야 합니다. 최초 실패와 정리 실패를 별도로
보존하고 정리가 확인되지 않으면 성공 결과를 내지 않습니다.

## 상태·실패·후속 채점

필수 흐름은 후보 → 검토한 미리보기/결정 → 소비된 전송 → 응답 확인 → 일치 stream/완료 →
엄격한 응답 검증 → 정리 확인된 관찰입니다. 거절·오래되거나 만료된 결정·통신 실패·중단·timeout·
무효 응답·정리 실패가 실행 가능한 성공을 만들거나 슬롯을 보충하면 안 됩니다. 내용 ID와 호출자
결정은 인증된 사람의 승인이 아닙니다.

후속 직접 관찰 타입을 호출자 제공 호스트 receipt와 분리합니다. 현재 collector로 런타임 출처를
만들거나 인증할 수 없습니다. 모드/반복마다 사례 7개·질문 기회 21개, 반복 1/2/3회에서 슬롯
14/28/42개를 모두 유지합니다. skipped/refused·missing·invalid·failed·interrupted·timeout을
정리 상태·시도 단계와 함께 구분합니다. 새 상태를 이전 collector 스키마로 강제하거나 점수를
높이려고 제거하지 않습니다.
정리가 확인되지 않거나 context/설정 무결성이 위반되면 남은 batch 전송을 멈추고 아직 전송하지
않은 슬롯은 명시적 skipped 이유와 함께 유지합니다. 정리가 확인된 일반 슬롯 실패 이후 계속할지의
정책도 미리 명시적으로 고정해야 하며 임의 재실행이나 암묵적 기본값으로 결정하지 않습니다.

별도 평가자가 정답 파일을 열기 전에 모든 검증 응답과 최종 실패 상태를 보존합니다. 후속 채점
연결은 missing을 `None`, invalid/실패/거절/skipped를 점수 없는 `[]`로 매핑하되 원래 실패 이유·분모를 유지해야
합니다. 확보 가능한 사용량·관찰 시간·사람 검토·의미적 인용 뒷받침·반복 변동은 별도 측정입니다.
답 전용 `0.1`로 설명/인용/검토 노력을 측정할 수 없다는 한계는 그대로입니다. 실제 실행이 성공해도
공개된 어시스턴트 작성 과제·미확보 독립 검토/blinding 한계는 남습니다.

## 구현 gate와 오프라인 수용 조건

1. 계정/네트워크/프로세스/정답 접근 없는 순수 소유 `0.2` codec부터 구현합니다. 모든 외부 필드/
   타입/연결·엄격한 JSON 상한·기존 내부 답 의미·원래/최종 메시지 해시·입력/정답 분리·두 모드
   포장 일치·이전 내부 답 재포장 반례를 테스트합니다.
2. 프로세스 경계를 추가하기 전에 정확한 버전별 평가 transport recipe를 검토합니다. 다른/중복/
   이른 event·설정/effort/모델 불일치·도구/승인·reroute·노출된 재시도·failed/interrupted 완료·
   EOF·상한/timeout/취소·불확실한 전송·정리 실패를 결정적 가짜 프로세스로 검사합니다. 가짜
   event는 실제 근거가 아닙니다.
3. 거절·오래되거나 만료된 결정·모든 누락/실패 슬롯을 보존합니다. 재시도·대체·context 재사용·부분
   출력 수용으로 완료 수치가 조용히 좋아지지 않는지 확인합니다.
4. 실제 동결 전에 후보 지시/스키마·정확한 transport/설정·순서·반복·측정/미측정 필드를 검토하고
   고정합니다. 현재 정답 값/작성 이력과 미확보 독립 검토 근거를 보존하며 이번 제안만으로 해결했다고
   하지 않습니다.
5. 그 뒤에만 정확한 소스·계정/모델·effort·시도 수·시간/사용량 한계를 포함한 명확한 실제 비교
   결정을 요청합니다. 기존 fixture/owner-repair 승인은 전용할 수 없습니다. 미리보기나 문서 예시로
   시험을 실행하지 않습니다. 해당 근거 없이 벤치마크 품질·근거 보조 개선을 주장하지 말고
   관찰 결과와 한계를 기술합니다.
