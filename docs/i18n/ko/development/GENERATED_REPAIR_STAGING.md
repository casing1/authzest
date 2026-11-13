<p align="center">
  <a href="../../../development/GENERATED_REPAIR_STAGING.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 입력 staging — 비공개 비활성 스냅샷

[문서 목차](../INDEX.md) · [비공개 workspace](GENERATED_REPAIR_WORKSPACE.md) ·
[Runtime profile](GENERATED_REPAIR_RUNTIME_PROFILE.md)

## 범위 — 2026-11-13 KST

이번 [#152](https://github.com/casing1/authzest/issues/152) 부분 단계는 추후 T/테스트·A/앱의 파일
mount용 비공개 입력 스냅샷을 준비합니다. 직접 관리하는 비활성 임시 파일로만 검사한 내부 POSIX
소스 API입니다. staged Python을 mount/import/compile/수집/실행하거나 Docker/AI를 호출하지 않고
executor·세션·CLI·UI도 활성화하지 않습니다. #152는 OPEN이며 파일 생성이 PoC 재현·수정 검증은 아닙니다.

`GeneratedRepairInputStage(copy, candidate, role, *, _before_create=None)`는 정확한 live
`GeneratedRepairWorkspace`만 받습니다. Before는 `ready-before`, after는 `applied-after`를
요구하며 복구됨·불확실·닫힌 checkpoint는 거부합니다. B/relay에는 앱/테스트 입력을 주면 안 되므로
staging을 거부합니다. 임의 목적지·재개·가져온 checkpoint 생성자는 없습니다.

## 분리된 비공개 부모와 고정 읽기 파일

새 stage는 원본 비공개 복사본의 형제 폴더로 만들며 추적 중인 복사본 내부를 바꾸지 않습니다.
바깥 폴더는 `0700`, `input`과 T의 `tests` 폴더는 생성 후 `0555`, 캡처한 일반 단일-link
소스/테스트는 `0444`입니다. 제한된 호스트 기록은 `input` **밖에** `0600`으로 둡니다.
추후 create 계획에는 고정 input 파일만 들어갈 수 있습니다.

| 역할 | 입력 파일                                     | 결합하는 원본 checkpoint          |
| ---- | --------------------------------------------- | --------------------------------- |
| T    | `app.py`, `tests/test_generated_ownership.py` | source·test·record와 정확한 phase |
| A    | `app.py`만, test 폴더/파일 없음               | source·test·record와 정확한 phase |
| B    | 거부, 할당 없음                               | 입력 staging 없음                 |

이 권한은 비공개 바깥 폴더를 노출하지 않고 추후 고정 UID 파일 mount를 가능하게 하기 위한 것입니다.
실제 Docker 공유·guest UID 접근·효과적 read-only mount·불변 파일시스템을 입증하지 않습니다.
신뢰 로컬 소유자가 권한을 바꿀 수 있으며 감지한 변경은 거부합니다. 악의적인 동시 동일 사용자 writer와
침해된 OS는 기존 가정 밖입니다.

## 캡처·할당·식별자 검사

기존 workspace 읽기는 원본 파일 6개와 추적 폴더를 검사합니다. Staging은 source/test/record의
`FileState`와 정확한 phase를 캡처하며 A도 test를 복사하지 않을 뿐 checkpoint에는 결합합니다.
신뢰 동기 `_before_create` hook이 거부할 수 있고 hook 뒤 첫 할당 직전에 checkpoint를 다시 비교합니다.
hook은 인증된 동의·새 시계가 아니며 추후 coordinator의 원래 결정/만료 재검사를 대체하지 않습니다.

held 디렉터리 FD·no-follow/nonblocking/exclusive I/O·제한된 UTF-8 원시 바이트·fsync·정확한
readback으로 이름과 생성 객체를 결합합니다. 폴더는 held-FD로 예상 항목 수+1까지만 살피고 예상 밖
파일을 거부합니다. 무제한 탐색은 하지 않습니다. Snapshot은 해시뿐 아니라
device/inode/mode/owner/group/link/size/mtime/ctime 식별자를 포함합니다.

`assert_current()`·`snapshot()`은 원본 checkpoint와 staged 폴더/파일을 모두 재검사합니다.
관리형 apply/restore·편집·record 변경·누락·symlink/hardlink/특수 파일·추가 항목·권한·동일 바이트의
inode 교체도 stage를 무효화합니다. 무효 상태는 고정하고 바이트를 되돌려도 같은 stage를 살리지 않습니다.
원본 복사본에는 쓰지 않습니다.

## 부분 상태 보존, 자동 복구 아님

초기화 오류는 시도 단계·파일별 진행·FD 정리 확인을 구분합니다. 생성이 확인된 경로는 보존하며 할당
불확실성을 쓰기 없음·확인한 소유 폴더로 표현하지 않습니다. 이름 충돌이 기존 대상을 열거나 지울 권한은
아닙니다. 자동 삭제·충돌 재시도·덮어쓰기·복구·재시작은 없습니다.

`close()`는 FD만 닫고 파일은 모두 보존합니다. 호스트 기록은 과거 생성 관찰이지 새 유효성·권한이
아니며 내보낸 기록으로 live stage를 다시 열 수 없습니다. 파일시스템/FD 정리의 보편적인 강제 시간
상한은 아닙니다. 파일별 제한은 여기서 지키지만 세션 전체 보존 예산은 추후 coordinator가 맡아야 합니다.

## 실행하지 않는 create 계획 연결

`prepare_create(profile, session_nonce, role_nonce)`는 기존 순수 인자 builder 전후로 live
stage를 검사합니다. 별도 `StagedCreatePlan`은 stage manifest를 고정 T/A create 데이터에 결합하며
작업 복사본·record를 mount하지 않습니다. 기존 plan 스키마를 준비 완료 기록으로 넓히지 않으며 선언한
엔진/이미지/config 식별자가 실제 존재한다고 입증하지 않습니다.

관찰한 호스트 파일과 런타임을 구분합니다. `filesystem_observed`는 true일 수 있지만
`runtime_invoked`·`execution_authorized`·`verified_fix`는 false, 인가는 unknown입니다.
파일 사실 일치·가져온 JSON이 동의·before 근거·소스 쓰기 권한을 만들지 않습니다. 추후 dispatcher는
각 효과 직전과 실행 뒤 **live** stage/현재 결정을 다시 검사하고 정확한 정지 컨테이너 입력·정리를
별도로 확인해야 합니다.

검토한 이미지/엔진/lock/기능·효과적 mount/자원 제한·attach/start/준비/제한 capture/정리·영속 세션
연결·설치 수용은 남았습니다. 새 소스 공유·실제 worker/생성 실행·운영 적용/복구·위험 수용·이슈 완료·
버전 변경·릴리스는 추가하지 않습니다.
