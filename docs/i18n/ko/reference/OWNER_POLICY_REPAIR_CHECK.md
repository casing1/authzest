<p align="center">
  <a href="../../../reference/OWNER_POLICY_REPAIR_CHECK.md">English</a> ·
  <strong>한국어</strong>
</p>

# 등록 수정 정책 검사 API

[문서 목차](../INDEX.md) · [개발 계획](../development/DEVELOPMENT_PLAN.md) ·
[검토한 설계](../development/OWNER_POLICY_REPAIR_CHECK_DESIGN.md) ·
[등록 수정 쌍](OWNER_POLICY_REPAIR_PAIR.md) · [추천](OWNER_POLICY_REPAIR_RECOMMENDATION.md)

## 가용성과 근거 — 2026-10-29 KST

[PR #110](https://github.com/casing1/authzest/pull/110)의 미출시 소스 구현은
`authzest.runner.owner_policy_repair_check`, 전용 고정 worker와 제한된 transport를 추가합니다.
관리자는 [설계와 오프라인 구현을 승인했습니다](https://github.com/casing1/authzest/pull/110#issuecomment-6459020000).
실제 worker 실행을 승인한 것은 아닙니다. `510377c`의 최초 구현 검증은 오프라인 계약, worker
정적 점검과 메모리 전용 scripted 프로세스 응답을 사용했습니다. 해당 테스트에서 작성한 boolean은
관찰된 정책 동작이 아닙니다. 이후 각각 별도로 승인한 **before 전용**, **after 전용** 실행을 아래와
같이 완료했고 두 1회 승인은 모두 소비됐습니다. After는 이후 문서 전용 커밋 `7f9c5ce`에서
실행했으며 런타임 소스는 `510377c`와 같았습니다.

새 CLI 명령·API endpoint·대시보드 화면은 없습니다. 공개 alpha.3에는 이 기능이 없습니다.
기존 #80 coordinator·worker·정책 등록·과거 관찰은 그대로 유지합니다. 이번 구현은 #81/#35/#82를
완료하거나 새 리뷰·실행·패치·발행 권한을 부여하지 않습니다. 별도 전달 결과는 아래에 기록합니다.

## 별도 승인한 before 수용 — 2026-10-28 KST

[별도 before 전용 승인](https://github.com/casing1/authzest/pull/110#issuecomment-6460245210)은
`510377c`에서 **2026-10-28 11:49:55 KST**에 고정 소스 실행 1회로 소비됐습니다. 앞선 오프라인
구현 검사와 Codex 추천 시도와는 별도입니다. Host 기록은 `31.640417` ms, 실행 `completed`,
종료 `0`, 자식/작업공간/전체 정리 모두 `confirmed`이며 출력 재검증도 통과했습니다.

| 기록한 식별 항목  | 값                                                                                    |
| ----------------- | ------------------------------------------------------------------------------------- |
| Before 계획 ID    | `owner-repair-check-141cb7a9bd522d851529d795241d7c4a9018ee1758f4a4285b83de12015e0829` |
| Worker SHA-256    | `9d81411933c8a42b33e3162acc16d4bea828a70b6c5a97c87c1fe0a9e41ee3f2`                    |
| 캡처 파일 SHA-256 | `acf78772b41331b1c26b8127787b94fe50c076c989e65d81d8b12663dfea0cbc`                    |

등록 사례 순서의 실제 boolean 8개는 `[true, true, false, false, false, false, false, true]`이며
예상값 일치 6개, 불일치 2개(`non-owner`, `exact-owner-no-normalization`)였습니다.
전체 `status`와 `comparison_status`는 `failed`, 이유는 `case-mismatch`입니다. 이는 **의도적으로
잘못된 before 정책의 예상한 시연 성공**이지 worker/transport 실패가 아닙니다. 통과를 만들려고
예상값을 변경하지 않았습니다.

Provider 호출은 `0`, 인가는 `unknown`, 적용/복구는 `not-run`을 유지했습니다. 과거 산출물
17개의 해시는 그대로였고 원본 main checkout은 깨끗했으며 #80도 변경하지 않았습니다.
이는 인증되지 않은 host 기록이지 독립 실행 증명·벤치마크·endpoint 인가·적용 파일 검증이 아닙니다.
해시는 보존한 바이트를 식별하지만 출처를 입증하지 않습니다. 캡처 해시는 `result.payload_json`만이
아니라 결정·결과·metadata를 포함한 전체 `capture.json` envelope를 대상으로 합니다. 여기서
새 fixture나 스키마를 커밋 대상으로 추가하지 않습니다.

이 before 1회 승인은 소비됐습니다. 해당 before 전용 시점에서 after는 미승인·미실행이었으며
이후의 별도 after 승인과 관찰은 아래에 기록합니다. Before 실행은 after를 승인하거나 자동으로
시작하지 않았고 before를 다시 실행할 때도 새 승인이 필요합니다.

## 별도 승인한 after 대조군 수용 — 2026-10-28 KST

[별도 after 전용 수용 기록](https://github.com/casing1/authzest/pull/110#issuecomment-6460474112)은
**2026-10-28 13:11:38 KST**의 승인한 실행 1회를 기록합니다. 당시 커밋은
`7f9c5ce5ef31ea8e49cd125e6c8459721b0cf6d7`이며 문서만 변경됐고 런타임 소스는 `510377c`와
같았습니다. Host 기록은 `36.152000` ms, 실행 `completed`, 종료 `0`, 자식/작업공간/전체 정리
모두 `confirmed`입니다. 출력 검증과 저장한 기록의 별도 오프라인 재검증을 통과했으며 후자는
어느 후보도 재실행하지 않았습니다.

| 기록한 식별 항목    | 값                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------- |
| After 계획 ID       | `owner-repair-check-a034e599a2dd51b862f06084f23e1924e79c6a517d691bf1b9ef9d0187d214f5` |
| 계획 바이트 SHA-256 | `63e3a48561468a2b0d648c899f2fdf765f2e71d19df40a8428681cd2d88d256c`                    |
| Worker SHA-256      | `9d81411933c8a42b33e3162acc16d4bea828a70b6c5a97c87c1fe0a9e41ee3f2`                    |
| After 소스 SHA-256  | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04`                    |
| 캡처 파일 SHA-256   | `16d235b8f3c9479821541f45e7284a917edd1386cadee8e74b65642ee7769714`                    |

등록 사례 순서의 실제 boolean은 `[true, false, false, false, false, false, false, false]`이며
일치 8개·불일치 0개입니다. 전체 `status`와 `comparison_status`는 `passed`, 이유는
`cases-match`입니다. 보존한 before/after 기록의 별도 순수 데이터 비교에서 수정 쌍/검토/사례/
worker/recipe/입력 binding의 일치를 확인했고 `non-owner`, `exact-owner-no-normalization`만
`true`에서 `false`로 바뀌었습니다. 후보/소스/계획 식별값은 의도대로 서로 다릅니다. 이는
보존 기록의 오프라인 점검이지 새 제품 비교 API나 인증된 실행 증명이 아닙니다.

캡처 파일 해시는 결과 JSON만이 아니라 결정/결과/metadata 전체 envelope를 대상으로 합니다.
Provider 호출 `0`, 인가 `unknown`, 적용/복구 `not-run`을 유지했습니다. Before 재실행·재시도·
AI/네트워크 호출·임의 저장소 실행·패치는 없었고 과거 산출물 17개 해시·원본 main checkout·#80은
그대로였습니다. 이는 등록 합성 대조군의 제한된 비인증 host 관찰이지 독립 벤치마크·일반 인가
보증·적용 파일 검증이 아닙니다.

두 후보의 승인은 모두 소비됐으며 재실행에는 새 승인이 필요합니다. 어느 관찰도 리뷰 활성화·
병합·패치·릴리스를 승인하지 않았습니다. 당시 관찰 시점에는 전달이 대기 중이었으며 이후 별도
승인한 완료 결과는 아래에 기록합니다. #81/#35/#82는 미완료입니다.

## 소스 전달 완료 — 2026-10-28 KST

[별도 최종 head 리뷰 승인](https://github.com/casing1/authzest/pull/110#issuecomment-6460920750) 뒤
`c265bf1`에 설정된 자동 리뷰 두 건은
[보고된 지적 없이 완료됐습니다](https://github.com/casing1/authzest/pull/110#issuecomment-6460924699).
[PR #110](https://github.com/casing1/authzest/pull/110)은 **2026-10-28 13:52:15 KST**에
`ea081e0e089dc6b87560016c150732ee913b9f35`로 병합됐습니다.
해당 소스 전달 단계만 완료했으며 전체 수정 흐름이나 릴리스 조건을 완료한 것은 아닙니다.
앞선 관찰 식별값과 소비한 승인은 그대로이고 적용 파일의 근거가 아닙니다. 다음 핵심 단계는
파일 식별값 연결 적용/검사/복구 설계의 별도 검토입니다.

## 고정 소스와 데이터 경계

입력은 변경하지 않은 `synthetic-owner-omission-v1` 수정 쌍과 검토된 사례 8개뿐입니다.
후보는 정확히 `before` 또는 `after`이며 기본값이나 `both` 모드는 없습니다. `before`는 의도적으로
잘못된 소유 합성 테스트 전용 텍스트이며 보고된 생산 코드 취약점이 아닙니다. `after`는 유지 중인
올바른 정책 대조군입니다. `policy.py`는 논리적 표시 이름이지 호출자 경로가 아닙니다.
호출자 소스·사례 대체·예상값 재정의·명령·모델 응답·정책 실행 callback을 받지 않습니다.

전체 계획은 등록 수정 쌍/검토 기록, 선택한 소스 바이트/해시, 순서가 있는 사례/예상값 8개,
입력 전용 행, 전용 worker 바이트/해시, 버전이 있는 recipe를 연결합니다. 도출한 계획 ID는
binding을 해시한 후 worker 입력에 추가합니다. 현재 식별값은 다음과 같습니다.

| 식별 항목            | 값                                                                 |
| -------------------- | ------------------------------------------------------------------ |
| 검사 ID              | `owned-owner-repair-check-v1`                                      |
| Recipe / coordinator | `1.0` / `repair-check-coordinator-v1`                              |
| Worker SHA-256       | `9d81411933c8a42b33e3162acc16d4bea828a70b6c5a97c87c1fe0a9e41ee3f2` |
| Before 소스 SHA-256  | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| After 소스 SHA-256   | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |

해시는 binding 변경을 감지할 뿐 독립 코드 증명이나 실행 권한이 아닙니다. 해시뿐 아니라 전체 계획과
[수정 쌍 참조](OWNER_POLICY_REPAIR_PAIR.md)를 확인하세요. 준비와 계획/결과 검증은 대상 경로를
읽거나 자식을 시작하거나 정책을 평가하지 않습니다.

## Python 인터페이스와 별도 결정

| 진입점                                                      | 의미                                                        |
| ----------------------------------------------------------- | ----------------------------------------------------------- |
| `prepare_owner_policy_repair_check(candidate)`              | 명시한 후보 하나의 전체 불변 오프라인 계획 준비             |
| `validate_owner_policy_repair_check_plan(raw)`              | 직렬화한 JSON을 재구성하고 정확한 현재 계획과 비교          |
| `OwnerPolicyRepairCheckSession(candidate)`                  | 전체 `plan`을 포함하고 실행 결정이 없는 live 세션 생성      |
| `session.decide(choice, plan_id=..., lifetime_seconds=...)` | 정확한 계획에 연결된 만료 가능한 프로세스 내부 선택 기록    |
| `await session.run()`                                       | 단일 시도를 소비하고 고정 자식 경로 전에 결정 확인          |
| `validate_owner_policy_repair_check_result(raw)`            | 기록 형식·현재 binding·비교 일관성 재검증; 출처 증명은 아님 |

Snapshot은 `payload_json`과 분리된 `to_dict()`를 제공하고 계획은 `check_plan_id`도 제공합니다.
세션은 `last_result`에 결과를 보존하며 취소 시에도 기록한 뒤 원래 취소를 다시 전달합니다.
가져온 JSON·직접 생성한 snapshot·모델 추천은 세션 결정을 부여하지 못합니다. Python 프로세스는
호출자가 제어합니다. 기록과 결정은 명시적으로 인증되지 않으며 악의적 호출자에 대한 접근통제
경계가 아닙니다.

선택지는 `pending`, `approved`, `declined`, `cancelled`입니다. 만료되지 않은 `pending`만
대체할 수 있고 다른 선택은 최종입니다. 잘못된 첫 결정이나 대체 결정은 해당 세션을 무효화합니다.
만료/재사용 선택·시계 역행·현재 계획 변경으로는 자식을 시작할 수 없습니다. 수명은 boolean이 아닌
유한한 숫자로 `0 < lifetime_seconds <= 300`이어야 하며 시계 값과 만료 시각은 유한한 0 이상의
값이어야 합니다. 사전 점검 실패를 포함해 첫 await 전에 시도 1회를 소비합니다. 동시 호출·재사용은
추가 시도를 얻지 못하며 재시도나 대체 경로도 없습니다.

동의를 기록하기 전에 새 전체 계획을 검토하세요. **Before 결정은 after를 승인하지 않습니다.**
After 검사에는 별도 세션과 해당 전체 계획에 대한 새 결정이 필요합니다. 과거 예상값 검토 결정,
소비한 Codex 공유 승인과 설계/구현 승인은 어느 후보의 실제 실행도 승인하지 않습니다.
따라서 이 문서에는 실제 실행 예제를 제공하지 않습니다.

다음 예제는 비활성 계획 데이터를 준비해 ASCII escape로 출력할 뿐 결정을 기록하지 않습니다.

```python
import json

from authzest.runner.owner_policy_repair_check import prepare_owner_policy_repair_check

plan = prepare_owner_policy_repair_check("before")
print(json.dumps(plan.to_dict(), ensure_ascii=True, indent=2))
```

## Worker recipe와 실패 처리

실행은 POSIX의 frozen이 아닌 Python 소스 환경만 지원합니다. 고정된 신뢰 interpreter 명령
`sys.executable -I -S -c`에 고정 내장 worker 텍스트, 상속하지 않는 최소 환경, 새 비공개 임시
작업 디렉터리와 새 프로세스 그룹을 사용합니다. 저장소를 복사/import하거나 계정/제공자/proxy
설정을 상속하거나 네트워크·FastAPI·HTTP·DB·설치 hook을 의도적으로 사용하지 않습니다.
이는 신뢰 프로세스 제어이며 **OS/네트워크 sandbox나 CPU/메모리의 강제 상한이 아닙니다.**
신뢰 interpreter/toolchain과 안정된 등록 코드가 가정입니다.

시작·입출력·완료는 합쳐서 **5초**이고 자식 시작 상태 확인·kill·reap은 **추가 1초**를 함께
사용합니다. Host 임시 디렉터리 생성/제거는 강제 wall-clock 상한이 없어 전체 6초 보장은 아닙니다.
Worker 입력은 최대 256 KiB, 출력은 최대 16 KiB이고 방어적 JSON 한계는 깊이 32·노드 8,192개입니다.
필드는 최대 scope 16개, 식별자/scope당 128자를 허용하지만 정확한 등록 내용 일치는 항상 필수입니다.

Worker stdin에는 정확한 요청 식별값과 순서가 있는 입력 전용 행 8개를 전달하며 예상값·소스 텍스트·
경로·모델 설명·검토자 산문은 전달하지 않습니다. Worker는 전체 요청을 검증한 뒤 내장 후보 하나만
컴파일합니다. Coordinator는 정확한 식별값과 순서가 있는 사례 ID/입력 해시/엄격한 boolean 행
8개만 받습니다. 누락·추가·순서 변경·중복·형 변환·부분·잘못된 출력은 관찰이 아닙니다.

시작 상태(`not-attempted`, `no-child`, `ambiguous`, `started`)는 자식/작업공간 정리 상태
(`not-needed`, `confirmed`, `unconfirmed`)와 별도입니다. 자식이 없다고 확인한 시작 실패도
작업공간 정리를 면제하지 않으며 디렉터리 정리 실패는 미확인으로 남습니다. 진행 중 시작의
결과가 불명확하면 자식이 없다고 주장할 수 없습니다. 반복 취소 시에도 제한된 자식 정리와 host
작업공간 정리 후 원래 취소를 유지하며 예외/stderr 텍스트는 결과 데이터로 쓰지 않습니다.

## 결과를 과장 없이 읽기

각 결과는 전체 정확한 계획·후보·예상값·null 또는 boolean 관찰과 별도의 실행/비교/시작/정리
진단을 유지합니다. 관찰 공개에는 종료 코드 0, 엄격한 출력 검증과 자식/작업공간 정리 모두의
확인이 필요합니다.

| 결과 필드           | 의미                                                                                                                |
| ------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `status`            | `not-run`, `passed`, `failed`; not-run은 수용한 비교가 없다는 뜻이며 반드시 프로세스 시도 자체가 없었다는 뜻은 아님 |
| `execution_status`  | `not-run`, `attempted`, `completed`; 실패/불명확한 시도는 완료가 아님                                               |
| `comparison_status` | `not-evaluated`, `passed`, `failed`; failed는 변경하지 않은 예상값과 불일치                                         |
| `cases`             | 별도 `expected`, `observed`, 사례별 `result`; unknown을 거절로 꾸미지 않음                                          |
| `cleanup_status`    | 별도 자식/작업공간 정리 근거에서 도출한 전체 상태                                                                   |
| `provenance`        | 인증되지 않은 `in-process-host-record`; 가져온 boolean이 실행됐다는 증거가 아님                                     |

시간 초과·취소·출력 초과·비정상 종료·잘못된 출력·과거/거절/지원하지 않는 결정·정리 미확인은
관찰 null과 사례 결과 unknown을 유지합니다. 비교를 완료해도 provider 호출은 `0`, 인가는
`unknown`, 적용/복구는 `not-run`입니다. 비교 `passed`는 endpoint 인가나 정책 전체의 정확성을
뜻하지 않습니다. 비교 `failed` 자체도 생산 코드 취약점 발견을 뜻하지 않습니다.

정적 추론에서 예상한 before의 `non-owner`, `exact-owner-no-normalization` 두 불일치와
after의 8개 일치는 위의 각각 별도 승인한 실행에서 관찰했습니다. 제한된 관찰이 고정 사례 밖의
정확성을 보장하지는 않습니다. 앞 공백을 포함한 입력 식별자를 유지하고 일치를 만들기 위해 예상값을 바꾸지 마세요.
신뢰할 identity/인증/scope/소유권 사실은
여전히 호출자가 제공하며 이 predicate가 인증하지 않습니다.

**실행한 내장 after는 대조군 관찰이지 적용 파일 검증이 아닙니다.** 애플리케이션 작업공간을
읽거나 편집·비교·복구하지 않습니다. 초기 API에는 자동 before→after 실행이나 통합 비교 helper가
없습니다. 소스 전달은 위 기록처럼 별도 완료됐으며 파일 식별값 연결 적용/검사/복구에는 자체
검토 설계와 별도로 범위를 정한 승인이 필요합니다. 이 내장 대조군의 관찰과 소비한 승인으로
이를 대신할 수 없습니다.

[검토한 설계](../development/OWNER_POLICY_FILE_REPAIR_DESIGN.md)에 따른 별도
[소유 파일 수정 API](OWNER_POLICY_FILE_REPAIR.md)를 PR #118에서 전달했으며 최초 검증은
임시 파일·scripted 프로세스를 사용한 오프라인 검증이었습니다. 이후 별도 승인한
[파일 흐름 수용](OWNER_POLICY_FILE_REPAIR.md#file-workflow-acceptance--2026-10-29-kst)은
2026-10-29 소스 커밋 `fb90c46`에서 실제 copied-before 검사 1회(6/8), 정확한 diff 수락,
적용 1회, 캡처한 적용 after 검사 1회(8/8), 복구 1회를 관찰했습니다. 이 소스 전용 API 기록이
내장 after를 적용 파일 검사로 바꾸거나 CLI 통합·새 실행 권한을 추가하지는 않습니다.
이 내장 대조군 API와 과거 관찰은 그대로 유지합니다.
