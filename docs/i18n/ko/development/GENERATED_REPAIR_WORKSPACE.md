<p align="center">
  <a href="../../../development/GENERATED_REPAIR_WORKSPACE.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 비공개 작업공간 — 오프라인 파일 I/O 기반

[문서 목차](../INDEX.md) · [검증 기반](GENERATED_REPAIR_VERIFICATION.md)

## 범위 — 2026-11-10 KST

[#152](https://github.com/casing1/authzest/issues/152)의 추가 오프라인 단계입니다.
**비공개 저수준 파일 I/O 경계**를 구현하며 실제 생성 수정 워크플로는 아닙니다.
생성/검증 미리보기 명령과 기본 비활성 실행기는 그대로입니다.
CLI·공개 API route·실제 결정/세션 조정기·이미지·컨테이너·worker·새 provider 요청은
이 도우미에 연결하지 않으며 #152는 계속 열어 둡니다.

유지보수 테스트는 직접 작성한 비활성 제안 문자열과 pytest 소유 임시 부모만 사용합니다.
이 바이트를 복사·교체·복구하는 것은 파일시스템 회귀 검사지, 실제 모델 패치의 운영 수용·
생성 테스트 실행·PoC 재현·검증된 수정이 아닙니다.
비공개 실제 생성 응답·계정 이력·과거 실제 복사본은 사용하지 않습니다.

## 비공개 경계

[`_generated_repair_workspace.py`](../../../../src/authzest/runner/_generated_repair_workspace.py)는
향후 별도로 통제할 조정기를 위한 내부 구현입니다. Python 호출자와 동기 guard callback을
신뢰합니다. 밑줄 이름·유효한 미리보기·파일 해시·callback 어느 것도 사용자를 인증하거나
실행/패치 권한을 부여하지 않습니다.

향후 조정기는 새롭고 만료되는 일회성 복사/diff/apply/restore 결정과 실제 독립 런타임 근거를
연결해야 합니다. 특히 호출자가 제공한 `data-only` HTTP 비교는 **before 검사 조건을 충족할
수 없습니다**. 이 도우미에는 그런 JSON을 런타임 증명으로 바꾸는 API가 없습니다.
모델 응답이나 UI에서 이 쓰기로 직접 연결하지 마십시오.

## 새 복사본과 고정 파일

`GeneratedRepairWorkspace(preview)`는 파일 효과 전에 현재 검증 미리보기 전체·요청/제안·
두 호스트 diff·유지보수 정의를 재검증합니다. `proposed-change`만 복사본을 만들 수 있습니다.
before 소스는 고정 관리 사례이고 after 소스/테스트는 검증한 정확한 제안 바이트입니다.
제안의 경로는 고정 표식이지 호출자가 선택하는 쓰기 대상이 아닙니다.

제품 기본 동작은 시스템 임시 위치에 새 비공개 디렉터리만 만듭니다.
기존 작업공간을 다시 열거나 journal을 세션으로 불러오거나 기존 checkout을 교체하거나 중단한
작업을 재개하지 않습니다. 비공개 `_parent`는 신뢰한 임시 파일 테스트용이지 산출물이 선택하는
대상이나 사용자를 위한 옵션이 아닙니다.

관리 파일은 다음과 같습니다.

```text
fresh-private-copy/
├── app.py                              # fixed before, then exact after, then before
├── tests/
│   └── test_generated_ownership.py      # materialized test; retained unchanged
├── before.txt                          # immutable source bytes
├── after.txt                           # immutable proposed source bytes
├── test.txt                            # immutable test bytes
└── record.json                         # bounded host bookkeeping, not an approval receipt
```

디렉터리는 현재 사용자 소유 `0700`, 파일은 현재 사용자 소유의 일반 single-link `0600`입니다.
root와 `tests`의 디렉터리 descriptor를 보유하고 열린 객체와 이름의 식별자를 모두 확인합니다.
초기화는 소스/테스트/snapshot의 정확한 재읽기·디렉터리 sync·초기 journal 영속 기록을 마쳐야
사용 가능한 before 상태입니다. 부분 초기화는 확인된 경로·실패 단계·파일 생성 정보를 남깁니다.
쓰기가 없었다고 주장하거나 근거를 삭제하거나 조용히 재시도하지 않습니다.

## 읽기·정확한 소스 교체·복구

`read_source()`·`read_test()`·`read_record()`는 바이트/식별자의 불변 `FileState`를 반환합니다.
소스/테스트는 기존 16,384바이트 상한과 정확한 UTF-8 바이트를 유지하며 개행을 정규화하지 않습니다.
읽기 전후 descriptor·파일 이름의 device/inode/mode/owner/group/link count/size/mtime/ctime을
확인합니다. 누락·symlink·hardlink·특수 파일·권한 변경·root/하위 디렉터리 교체·동일 바이트의
inode 교체도 검토한 상태로 간주하지 않습니다.

`apply_source(expected, guard=...)`는 `app.py`만 정확한 after 바이트로 교체하고,
`restore_source(expected, guard=...)`는 확인된 적용 파일을 정확한 before로 돌립니다.
테스트·불변 snapshot·추적 journal도 그대로인지 확인합니다. 동기 guard는 `None`으로 정상
완료해야 하며 동의가 아닌 재확인 hook입니다. intent journal·소스 commit 전에 한 번 호출하지만
정확한 비공개 staging 파일 준비는 callback보다 앞설 수 있습니다. 재진입 전환은 거절합니다.
이후 파일 상태를 다시 확인합니다. 이 읽기에도 시간이 걸리므로 실시간 만료 보장이나 원자적 결정/쓰기는 아닙니다.
소스 교체 전에 미확인 작업 의도를 영속 기록하고 소스 fsync·재읽기가 성공한 뒤에만 journal을
확정합니다. 잘못된 단계·오래된 입력·사용자 편집은
덮어쓰는 대신 거절해야 합니다.

복사 직후 기준은 **before 앱+생성 테스트**입니다. 테스트 생성은 복사에 속하고 이후 소스 적용은
앱만 바꿉니다. restore는 테스트/근거를 보존하며 테스트가 없던 원본 tree를 복원하거나 생성
테스트를 지우거나 원본 checkout을 수정하지 않습니다. 이 단계는 원자적 두 파일 패치가 아닙니다.

## 실패와 기록

사용 가능한 before·확인된 after·복구한 before·미확인 상태를 구별합니다. 제한된 호스트 journal은
현재 미리보기/파일 식별자와 파일 작업 상태를 묶되 실행은 미실행, 접근통제 보장은 unknown으로
유지합니다. 점검 가능한 기록이지 인증된 승인 영수증이나 불러올 수 있는 실행 권한이 아닙니다.

소스 교체 전에 미확인 쓰기 의도를 기록합니다. 이는 적용·복구 성공이 아니며 재개 권한도 아닙니다.
교체 후 fsync·재읽기·최종 journal 실패는 이미 파일을 바꿨을 수 있습니다. 이런 결과는 미적용이 아니라
교체 시도/적용 후 미확인으로 알려야 합니다. 미확인 상태·근거 변경·영속 기록 실패는 후속 효과와
프로그램 복구를 차단하며 수동 점검용으로 복사본을 보존합니다. 새 callback도 감지된 편집을
덮어쓸 권한을 주지 않습니다. 인터럽트 metadata도 같은 구분을 유지해야 합니다.

정리는 정확히 방금 만든 staging 항목만 대상으로 합니다. 정리 미확인을 조용한 성공으로 바꾸거나
사용자가 선택한 경로로 대상을 확대하지 않습니다. `close()`는 descriptor만 닫고 복사본·테스트·
journal을 삭제하지 않습니다. 자동 재시도·프로세스 재시작·journal 재개·강제 rollback·부분 근거로
성공 처리는 없습니다.

## 한계와 다음 연결

필요한 descriptor/no-follow 기능이 있는 POSIX non-frozen 소스 설치만 지원합니다.
다른 플랫폼은 이 파일 경계를 거절해야 하며 이식 가능한 일반 scan/preview·계약 지원과는
별개입니다. 해당 경로에 Docker 의존성을 추가하지 않습니다.

비공개 권한·해시·원자적 rename은 OS sandbox나 악의적 동일 사용자 동시 작성자에 대한 원자적
CAS가 아닙니다. 신뢰한 운영자가 동시 작성을 배제해야 합니다. 디렉터리 생성·여러 파일 쓰기·
앱 교체·journal은 하나의 트랜잭션이 아니며 파일시스템 호출의 전체 시간 상한은 없습니다.

다음 조정기는 효과 전에 실제 단계 결정을 소비하고 유한 monotonic 만료·일회성 시도를 강제하며
적용 전에 유효한 실제 before 근거를 요구해야 합니다. 실제 캡처 바이트 검사와 guest 정리 확인도
연결해야 합니다. 기본 실행기는 계속 비활성이고 이 파일 도우미는 우회 실행 경로가 아닙니다.
생성 pytest 보고는 신뢰하지 않는 보조 데이터이며 독립 대조·실제 after 파일 관찰·거절/복구·정확한
설치 후보 수용은 여전히 필요합니다. 로컬 읽기 전용 UI와 릴리스도 별도 조건입니다.
