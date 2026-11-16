<p align="center">
  <a href="../../../development/GENERATED_REPAIR_SESSION.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 세션 — 보호된 비공개 복사본 흐름

[문서 목차](../INDEX.md) · [비공개 파일 기반](GENERATED_REPAIR_WORKSPACE.md) ·
[CLI 흐름](../guides/GENERATED_FILE_WORKFLOW.md)

## 현재 범위 — 2026-11-16 KST

[#152](https://github.com/casing1/authzest/issues/152)의 소스 구현은 현재 로컬 결정을 비공개 복사,
before 검사, 정확한 diff 수용·적용, 새 after 검사와 복구에 연결합니다. 명시적 opt-in 경로이며
기본 세션은 복사 생성과 비활성 before 준비만 허용합니다. 어느 모드도 저장된 기록을 권한으로 가져오지 않습니다.

테스트는 소유한 비활성 파일, 가짜 phase/커널 응답과 기존 신뢰 회귀 검사 자식을 사용합니다.
새 실제 AI·Docker·생성 코드 실행·운영 패치·릴리스 수용을 주장하지 않습니다. 현재 소스의 재빌드 이미지와
별도 범위의 설치형 수용은 남아 있으며 #152와 #150은 열린 상태입니다.

## API와 신뢰한 조정

[`_generated_repair_session.py`](../../../../src/authzest/runner/_generated_repair_session.py)는 다음을 제공합니다.

- `GeneratedRepairSession(preview, clock=...)`: 기본 복사·비활성 준비 동작입니다.
- `GeneratedRepairSession(preview, runtime_profile=..., runtime_guard=..., clock=...)`: 필수 신뢰
  동기 guard와 현재 profile에 결합한 opt-in 흐름입니다. Profile 선언은 준비 완료가 아닙니다.
- `prepare(stage)`와 `decide(stage, choice, plan_id=..., lifetime_seconds=...)`: 전체 현재 계획을
  확인하고 최종 선택 `approved`·`declined`·`cancelled`를 한 번 기록합니다.
- `create_copy()`·`run_before()`·`accept_diff()`·`apply_source()`·`run_after()`·
  `restore_source()`: 이 순서로 독립 단계의 시도를 소비합니다.
- `prepare_before()`: 기본 비활성 readiness 검사를 유지하며 phase를 실행하지 않습니다.
- `result()`와 `close()`: 복사본·근거를 보존하면서 제한된 과거 요약을 내보내거나 descriptor를
  닫습니다. 가져오기·재시작·재개 API는 없습니다.

Python 호출자·guard·시계는 신뢰한 조정 코드이지 사람의 인증이나 sandbox가 아닙니다.
CLI는 새 런타임 검토와 개별 단계 문구를 추가하며 상호작용은 가이드를 참고하세요. 복사의 비공개
`_parent` 인자는 소유 테스트용이며 사용자가 선택하는 목적지가 아닙니다.

## 현재 결합과 원래 만료 시각

계획은 현재 시나리오·제안·소스/테스트·호스트 계산 diff, 세션 nonce, profile 식별자, 앞서 수용한
결과와 실제 관리 파일 식별자/해시에 결합합니다. 후속 단계는 예상한 `ready-before`·
`applied-after`·`restored-before` 상태를 캡처합니다. 바이트·같은 바이트의 inode·snapshot/journal·
디렉터리가 바뀌면 승인을 조용히 재결합하지 않고 계획한 작업을 거부합니다.

계획은 최초 생성 시각과 최대 300초 뒤의 원래 만료를 유지합니다. 재준비로 갱신하지 않으며 나중 결정은
만료를 줄일 수만 있습니다. 만료 시각과 같아도 만료입니다. 선택은 최종적이고 전제 실패여도 동작은
시도 한 번을 소비합니다. 재진입·재사용·잘못된 시계를 거부하며 파일시스템 작업 전체의 보편적 시간
상한을 보장하지 않습니다.

활성 세션은 소스 적용·복구 모두 workspace의 선택형 `commit_guard`를 항상 제공합니다.
영속 pending intent와 최종 추적 파일·staging 검사 뒤에 원래 profile/결정·소스/테스트·pending 기록을
재검사하고 `os.replace` 전 monotonic 시계를 마지막으로 확인합니다. 이때 만료·취소되면 앱 rename은
수행하지 않지만 기록한 pending journal은 `state-unconfirmed`로 남아 점검해야 하며 재시도·강제 복구하지
않습니다. Dispatch 제한이지 파일시스템 완료나 원자적 compare-and-swap 보장이 아닙니다.
악의적인 동일 사용자 동시 작성자는 배제해야 합니다.

## Before·적용·복구

Before/after는 현재 호출이 직접 반환한 phase 객체만 소비합니다. 후보·세션/계획/profile 식별자,
캡처 소스/테스트 해시·소유 객체·정리를 확인하고 완전한 B 수집을 관리하는 17개 사례 / 21개 요청에
대해 독립 재계산합니다. 전달 JSON·pytest 출력·시작 신호·위조 ready flag는 before 근거가 아닙니다.

T의 before 종료 1과 after 종료 0은 별도 보조 관찰이며 assertion 진위나 일반적인 인가 증명이 아닙니다.
완전한 호스트 비교와 정리 확인은 독립 조건입니다. 고정 이미지 진입점은 target/tool import 전에
지원하는 커널 제어를 검사하고 조건 누락·불일치 시 종료 78로 거부합니다. 좁은 커널 보고 설정의
관찰이지 탈출 불가 증명이나 자원 부하 벤치마크가 아니며 현재 이미지 내용 검토도 필요합니다.

확인한 의도된 before 결과만 정확한 소스 diff 수용과 적용을 엽니다. 기존 workspace는 새 비공개
복사본의 검토한 `app.py` 바이트만 교체하고 생성 테스트는 유지합니다. After는 새 staging 입력을
사용합니다. After 실패여도 적용 파일과 정리를 확인한 경우에만 별도 검토한 복구를 제안할 수 있습니다.
변경·불확실한 파일, 잘못된 기록, 미확인 정리는 무조건 복구하지 않고 점검해야 합니다.

자동 복구·삭제·재시도는 없습니다. EOF/Ctrl-C/SystemExit는 추가 상호작용을 중단하고 완료·불확실 효과를
계속 표시합니다. 복구한 before 파일은 과거 after 통과를 물려받지 않으며 복구로 검사를 다시 실행하지 않습니다.

## 예산과 결과 보존

Before와 after는 누적 2 MiB 근거 예산 하나를 공유합니다. 전체 계획을 계산하고 효과 전에 제한된 최종
요약·복구 계획 공간을 예약하여 일반적인 근거 예산 소진이 복구 기록 공간을 조용히 소비하지 않게 합니다.
원본 출력은 비공개 phase 기록에 보존하고 세션은 제한된 요약·근거 참조를 내보냅니다.

각 phase는 원래 40초, 누적 준비 10초, 추가 공유 정리 10초를 유지합니다. CLI 출력은 256 KiB를 공유하며
일반 수집 224 KiB와 정리 예약 32 KiB를 사용합니다. 파일시스템·커널 작업 전체의 보편적 시간 상한은 아닙니다.

결과는 인가 unknown, `verified_fix: false`, 구분된 적용·복구 상태를 유지합니다.
쓰기가 불확실하면 무효과로 추정하지 않고 `applied: null`과 명시적 `current_copy_state`를 표시합니다.
확인된 복구 뒤에도 기록한 과거 적용은 true로 남을 수 있습니다. 현재 소스 흐름은
구현했으며 실제 설치형 수용, 로컬 읽기 전용 결과 UI
[#153](https://github.com/casing1/authzest/issues/153)와 정식 릴리스는 남아 있습니다.
