<p align="center">
  <a href="../../../reference/OWNER_POLICY_FILE_REPAIR.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소유 정책 파일 수정 API

[문서 목차](../INDEX.md) · [개발 계획](../development/DEVELOPMENT_PLAN.md) ·
[검토한 설계](../development/OWNER_POLICY_FILE_REPAIR_DESIGN.md) ·
[수정 추천](OWNER_POLICY_REPAIR_RECOMMENDATION.md) ·
[내장 대조군 검사](OWNER_POLICY_REPAIR_CHECK.md)

## 가용성과 근거 — 2026-10-29 KST

미출시 소스 구현은 [PR #118](https://github.com/casing1/authzest/pull/118)에서 소개합니다.
관리자는
[설계 `29d8c82`와 오프라인 구현을 승인했습니다](https://github.com/casing1/authzest/pull/118#issuecomment-6486618422).
실제 파일 정책 worker 실행이나 수정을 적용하는 운영자 인수 검증을 승인한 것은 아닙니다.
이번 단계의 검증은 순수 데이터 검사, 임시 파일 I/O, worker 정적 점검과 모의 프로세스 응답을
사용합니다. 작성된 모의 응답은 관찰된 정책 동작이 아닙니다. 정확한 테스트 결과와 대상 커밋은
PR에 별도로 기록하며, 여기서는 새 worker의 실제 인수 검증을 주장하지 않습니다.

활성 파일 흐름은 필요한 descriptor 상대경로 파일시스템 기능과 신뢰하는 로컬 운영자가 있는
**POSIX의 non-frozen Python 소스 모드만** 지원합니다. 새 CLI 명령·API endpoint·GUI 화면은
없습니다. 공개 alpha.3에는 이 구현이 없습니다. #81/#82/#35는 열린 상태를 유지합니다.
이 문서와 오프라인 테스트 통과는 리뷰 활성화·병합·실행·패치 인수 검증·릴리스 권한을 부여하지
않습니다. 기존 #80/#110 대조군과 과거 관찰은 그대로이며 새 파일 worker의 실행 근거가 아닙니다.

## 지원 입력과 API 경계

등록된 `synthetic-owner-omission-v1` before/after 쌍, 호스트가 도출한 단일 파일 diff와
검토된 사례 8개만 지원합니다. 새 API는 기존 checkout·정책 경로·호출자가 정한 소스·AI가
생성한 대체 코드·실행 파일·사례 집합을 받지 않습니다.

순수 적용 데이터 계층은
[`authzest.codex.owner_policy_file_repair`](../../../../src/authzest/codex/owner_policy_file_repair.py),
활성 coordinator는
[`authzest.runner.owner_policy_file_repair`](../../../../src/authzest/runner/owner_policy_file_repair.py)입니다.

| API 경계                                                                      | 동작                                                                                                                   |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `prepare_owner_policy_file_repair(request, recommendation)`                   | 전체 등록 입력을 재검증하고 독립된 적용 데이터를 생성합니다. I/O·제공자 호출·실행·승인은 없습니다.                     |
| `validate_owner_policy_file_repair(raw)`                                      | 적용 데이터를 재구성하고 검사하며 권한을 가져오지 않습니다.                                                            |
| `OwnerPolicyRepairFileSession(application)`                                   | 적용 데이터를 재검증하고 메모리 내 세션 상태만 생성하며 파일은 만들지 않습니다.                                        |
| `create_copy()`                                                               | `registered-change`에 대해서만 새 비공개 임시 복사본 하나를 명시적으로 만듭니다. 검사나 수정 적용은 시작하지 않습니다. |
| `prepare(stage)` / `decide(stage, choice, plan_id=..., lifetime_seconds=...)` | 단계 미리보기와 별도의 활성 선택을 기록합니다. 그 단계의 검사나 파일 교체는 수행하지 않습니다.                         |
| `run_check(stage)`, `accept_diff()`, `apply()`, `restore()`                   | 현재 계획·결정·선행 조건에 따르는 별도 1회 작업입니다.                                                                 |
| `result()` / `validate_owner_policy_file_result(raw)`                         | 인증되지 않은 checkpoint를 내보내거나 검증합니다. 현재 파일 증명이나 재개 가능한 세션이 아닙니다.                      |
| `close()`                                                                     | 파일을 삭제하지 않고 복사본의 descriptor를 해제합니다. 실행 중인 검사가 있으면 거절합니다.                             |

`no-change`와 `unknown`도 정상 추천 결과입니다. 적용 데이터는 해당 상태를 보존하며,
두 결과에 대한 복사본 생성 요청은 디렉터리를 만들지 않고 `recommendation-has-no-change`를
보고합니다. `_parent` 주입 지점은 임시 파일 테스트 전용이며 지원하는 목적지 옵션이 아닙니다.

활성 세션은 복사본 생성 전에 전체 application을 추가로 **32 KiB**로 제한합니다.
순수 추천/application 계약은 기존 envelope 규칙을 유지합니다. 더 작은 활성 예산으로 캡처 검사
계획 두 개를 보존 checkpoint에 넣을 공간을 확보합니다. 세션 이력은 **이벤트 256개**로 제한하며
해당 예산 소진이나 checkpoint 직렬화 실패는 증거를 미확인으로 표시하고 후속 동작을 차단합니다.
전체 JSON 바이트·깊이·노드 제한도 계속 적용합니다.

## 별도의 계획과 결정

| 단계           | 필요한 checkpoint와 효과                                                                      |
| -------------- | --------------------------------------------------------------------------------------------- |
| `before-check` | 변경되지 않은 새 복사본에서 캡처한 before 바이트를 별도로 실행합니다.                         |
| `diff`         | 유효하게 완료된 baseline 뒤에 정확한 등록 diff를 수락하며 적용하지는 않습니다.                |
| `apply`        | baseline·diff 수락과 또 다른 선택 뒤에 추적한 before 바이트를 등록 after 바이트로 교체합니다. |
| `after-check`  | 확인된 적용 snapshot과 또 다른 선택 뒤에 캡처한 after 바이트를 별도로 실행합니다.             |
| `restore`      | 확인된 적용 상태와 또 다른 선택 뒤에 등록 before 내용을 새 inode로 복구합니다.                |

각 계획은 세션·단계·generation·적용 데이터·등록 정보·현재 파일/루트 식별값과 바이트·관련 선행
완료 기록에 연결됩니다. 검사 미리보기에는 worker 소스·recipe·사례·검토한 예상값도 포함됩니다.
ID만이 아니라 전체 미리보기를 읽어야 합니다.

선택은 `pending`·`approved`·`declined`·`cancelled`입니다. 유효한 pending 결정만 변경할 수
있으며 승인은 정확한 계획에 연결되고 원래 계획의 **최대 300초** 유효기간을 넘길 수 없습니다.
효과 경계에서 유한한 단조 시간·만료·입력 및 파일 식별값 변경을 재확인합니다. 작업 호출은 실패한
사전 검사를 포함해 첫 await나 효과 이전에 해당 단계의 시도를 소비합니다. 자동 재시도, 종료되거나
만료된 결정의 재개, JSON에서 승인 가져오기는 없습니다. 이는 로컬 흐름의 gate이지 인증된 사람의
서명이 아닙니다.

사례 예상값과 불일치해도 완전한 baseline은 유효한 관찰이며 diff 수락으로 이어질 수 있습니다.
없거나 유효하지 않은 baseline은 허용하지 않습니다. 추적한 적용 상태와 증거 저장이 확인된 한,
after 검사 거절·취소·실패 자체가 별도의 복구 선택을 막지는 않습니다.

## 캡처 소스 worker와 제한

새 worker는 내장 대조군 worker와 별개입니다.

- 검사 ID: `owned-owner-file-repair-check-v1`.
- Worker SHA-256: `33413d680ac8e00f514d5897aca2289527cfccfd8a1fccdebb179c774377491d`.
- 소스: [`_owner_policy_file_worker.py`](../../../../src/authzest/runner/_owner_policy_file_worker.py).

호스트는 소유한 `policy.py`를 안전하게 읽고 경로가 아닌 캡처한 정확한 UTF-8 소스를 전송합니다.
worker는 등록 바이트와 닫힌 protocol을 검증한 뒤 **실제로 받은 소스**를 컴파일하며 내장 정책으로
대체하지 않습니다. 예상 정답과 추천 설명문은 worker 입력에 넣지 않습니다. 수용되는 출력에는
연결된 boolean 관찰 8개, 정상 종료, 확인된 자식/worker 디렉터리 정리와 실행 후에도 일치하는
파일 snapshot이 필요합니다.

고정 recipe는 신뢰하는 `sys.executable -I -S -c`, 고정 worker 소스, 새 비공개 worker 디렉터리와
최소 환경변수를 사용합니다. 제한은 소스 32,768바이트, 입력 256 KiB, 출력 16 KiB, 시작·입출력·
완료 5초와 자식 정리 추가 1초를 포함합니다. 파일시스템 호출의 wall-clock 시간은 강제 상한이
없습니다. **OS sandbox가 아니며** CPU·메모리·네트워크 격리를 강제하지 않습니다. 제공자 호출,
네트워크 작업, 설치, FastAPI·HTTP 테스트는 이 recipe에 포함되지 않습니다. 실제 실행은 구체적인
소스와 계획 식별값에 대한 별도 승인이 필요합니다.

## 보존 파일·결과·복구

새 복사본은 `0700` 루트와 `0600` `policy.py`를 사용하고 `before.txt`·`after.txt`·`record.json`
증거를 보존합니다. 읽기는 descriptor/파일명 metadata와 바이트를 대조합니다. symlink, 일반 파일이
아니거나 링크가 여러 개인 파일, 변경된 소유권·모드·루트와 이후 사용자 편집은 거절합니다. 적용과
복구는 등록 바이트를 staging한 뒤 atomic rename을 수행하고 영속성과 상태를 확인합니다.
복구 대상은 내용이지 원래 inode나 임의 checkout metadata가 아닙니다. atomic rename은 동시
접근하는 동일 사용자 writer에 대한 compare-and-swap이 아니므로 동시 수정을 피해야 합니다.

결과는 적용·실행·예상값 비교·복구·파일 연결·증거 저장·소비된 결정을 구분합니다. 없거나 확인되지
않은 관찰을 거부 결과나 비교 통과로 만들어 내지 않습니다. `authorization_status`는 `unknown`,
이 단계의 `provider_calls`는 `0`이며 출처는 인증되지 않습니다. 기록한 통과는 checkpoint에서
캡처한 바이트에 관한 것이지 endpoint의 접근통제나 파일의 영구적인 정확성을 뜻하지 않습니다.

성공·거절·취소·실패 후에도 복사본을 보존합니다. 초기화 실패 시 확인된 생성 경로가 있으면
보존하지만 `record.json`이 존재함을 입증하지는 않습니다. 감지한 사용자 편집은 덮어쓰지 않고 후속
효과를 차단합니다. 교체 후 committed 상태를 확인할 수 없으면 `state-unconfirmed`로 보고하고
후속 검사와 프로그램을 통한 복구를 막습니다. 정책 snapshot이 확인됐더라도 증거 쓰기 실패는
후속 효과를 차단합니다. 이 경우 보존한 경로를 수동 점검해야 합니다. 인터럽트 checkpoint는 원래
예외에 첨부될 수 있으며 불확실한 쓰기를 안전하게 롤백했다고 보고하지 않습니다.

파일 교체와 증거 기록은 하나의 transaction이 아닙니다. 자동 rollback·삭제·프로세스 재시작/재개·
가져온 receipt를 통한 복구는 없습니다. 저장한 JSON checkpoint 검증은 데이터 일관성만 검사하며
그 경로를 다시 열거나 출처를 인증하거나 작업을 승인하지 못합니다. 다음 인수 검증 단계에는 before
검사·정확한 diff·적용·after 검사·복구 각각의 결정이 필요합니다. 읽기 쉬운 CLI 연결은 #82에서
별도로 진행합니다.
