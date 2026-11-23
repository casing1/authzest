# 외부 비공개 파일 세션 (S2)

[문서](../INDEX.md) · [English](../../../reference/REPOSITORY_FILE_SESSION.md) · 한국어

이 소스 Python API는 [#204](https://github.com/casing1/authzest/issues/204)와
[외부 파일 흐름 설계](../development/REPOSITORY_FILE_WORKFLOW.md)의 비공개 **파일 경계**를 구현합니다.
모델 클라이언트, 대상·테스트 실행, CLI/GUI 조작 흐름, 원본 프로젝트 쓰기는 없습니다. `repo-suggest`는
계속 제안 전용 결과를 반환하며 이 API를 호출하지 않습니다. 패키지 worker와 기존 GUI도 유지합니다.

## Live 입력과 소유권

`capture_repository_origin(root, source, policy, contexts=())`는 최초 캡처한 루트·부모·파일 descriptor와
정확한 선택 바이트를 보유하는 `RepositoryOrigin`을 반환합니다. `snapshot`은 콘텐츠 전용
`RepositoryInput`이며 그 자체로 최신 상태를 입증하지 않습니다. `verify(selection)`은 최초 선택 전체,
정확한 바이트와 최초 파일 식별자를 열린 descriptor 및 현재 경로명이 가리키는 파일과 대조합니다.
같은 바이트를 가진 다른 inode로의 교체, 편집, 메타데이터·링크 변경, 경로 교체를 거부합니다.
선택하지 않은 파일은 발견·복사·실행하지 않으며 무관한 디렉터리 내용 변경은 허용합니다.

`RepositoryFileSession(origin, request, response, copy_plan)`은 현재 검증한 요청·응답, 일치하는 S1 계획과
정확한 live origin으로만 생성합니다. 생성이 성공하면 파일 생성 없이 descriptor 소유권을 세션에
넘깁니다. 같은 origin을 두 번째 세션에 넘길 수 없습니다. 생성 실패는 origin을 가져오거나 닫지 않으며
기존 소유자가 책임을 유지합니다. 생성 과정 전체의 동일성을 주장하려면
향후 조작 흐름은 공유·생성 **전에** 이 origin을 캡처해야 합니다. 나중에 새 origin을 캡처하면 새로운
기준만 설정합니다. 현재 콘텐츠 전용 `repo-suggest` 캡처로는 이전 inode 동일성을 복원할 수 없습니다.

호출자와 동기 clock은 신뢰하는 Python 조정 수단입니다. 입력 JSON, 해시, 입력한 확인 문구는 사람,
제공자 또는 새 모델 호출을 인증하지 않습니다. 향후 조작 흐름에서 이 별도 관찰을 직접 결합해야 합니다.
객체는 복제·pickle 직렬화하거나 경로로 다시 열거나 저장된 요청·계획·결과·journal JSON에서
복원할 수 없습니다. 동작은 생성한 프로세스와 세션 스레드에 묶입니다. 비공개 필드는 해당 프로세스에서
실행하는 임의 코드에 대한 방어 수단이 아닙니다.

## 현재 계획과 정확한 전이

지원하는 API 순서는 다음과 같습니다.

```text
capture_repository_origin(...) → build_repository_request(origin.snapshot, model)
validate response → prepare_repository_copy_plan(request, response)
RepositoryFileSession(origin, request, response, copy_plan)
prepare(step) → review complete plan → decide(the_same_plan, exact_confirmation)
perform(the_same_decision)

copy → accept-diff → apply → restore → close
```

`prepare(step)`은 동결된 `RepositoryFilePlan`을 반환합니다. 전체 선택 입력, 검증한 제안과 정확한
호스트 계산 diff, S1 material 식별자, 로컬 원본·비공개 경로와 현재 비공개 파일 식별자를 포함합니다.
이 자료는 비공개 소스 자료로 취급하세요. 전체 로컬 검토는 256 KiB로 제한하며 초과하면 할당 전에
거부합니다. 기존 선택·material·journal 제한도 유지합니다. 원자 교체에는 보존 material·journal 외에
최대 64 KiB의 추가 staging 파일 하나가 필요하며 실패한 staging은 보존합니다. 새 파일 세션 계약이며
수용된 GUI 가져오기 형식이 아닙니다.

`decide(plan, confirmation)`은 정확한 현재 계획 객체, 세션, revision과 최초 만료에 묶인
`RepositoryFileDecision`을 반환합니다. 내용이 같은 객체를 재구성해도 거부합니다. 각 단계는 한 번만
사용할 수 있으며 최초 단조 clock에서 최대 300초 동안 유효합니다. 반복 준비는 기한을 초기화하지
않고 같은 계획을 반환합니다. 만료, 재사용, 잘못된 단계, 프로세스·스레드 불일치와 재진입 동작은
권한을 만들지 못합니다. 저장 기록 재개나 자동 승인은 없습니다.

- **copy:** 원본 선택·최초 식별자를 다시 검증하고 새 비공개 루트 하나를 할당하기 직전에 만료를
  확인합니다. `0700` 디렉터리, `0600` 단일 링크 일반 파일과 배타적 no-follow 동작으로 S1 선택 소스
  배치만 생성합니다. 비공개 트리와 완료 journal을 정확히 다시 읽을 때까지 초기화를 pending으로 기록합니다.
- **accept-diff:** 정확한 현재 변경을 별도로 수용하고 그 로컬 결정을 영속 기록합니다. 소스를 교체하지 않습니다.
- **apply:** 현재 비공개 before 소스와 불변 근거를 요구합니다. pending 의도를 영속 기록하고 정확한
  after 바이트를 staging한 뒤 소스 교체 직전에 현재 결정을 확인합니다. 정확한 새 소스를 다시 읽고
  완료를 영속 기록합니다.
- **restore:** 현재 비공개 소스가 수용한 after와 같고 before snapshot이 캡처한 before와 같아야 합니다.
  해당 소스만 before로 교체하고 테스트·문맥·snapshot·이력을 보존합니다. 빈 before 소스도 지원합니다.
  복사 후의 원본 변경은 독립된 비공개 복구를 막지 않으며 원본을 덮어쓰지도 않습니다.

모든 journal 교체는 현재 단계의 최초 기한 안에서 별도의 최종 검사를 수행합니다. live 파일 handle은
변할 수 있는 journal을 마지막으로 검증한 자체 commit 바이트·식별자와 비교하며 영속 다시 읽기 후에만
이 기준을 갱신합니다. 저장된 JSON을 상태 근거로 신뢰하지 않습니다. 원본 입력의 최신 상태는 복사
전에만 확인하며 독립된 복사본을 복구할 때는 확인하지 않습니다.

## 실패와 관찰의 한계

동작 전에 비공개 트리 항목, 권한, 단일 링크 일반 파일 식별자와 정확한 바이트를 검사합니다.
사용자 편집, 추가 항목, 링크 또는 메타데이터 변경은 쓰기를 거부합니다. 교체에는 배타적 형제 staging,
파일 sync, 최종 결정 guard, 원자적 rename, 디렉터리 sync와 다시 읽기를 사용합니다. 최종 guard와
rename 사이에는 파일시스템 작업이 없습니다. 파일시스템·clock·영속성 실패를 성공한 rollback으로
가정하지 않습니다. 이 검사는 적대적인 동일 사용자 writer에 대한 compare-and-swap, OS sandbox 또는
전체 파일시스템 작업의 엄격한 시간 제한이 아닙니다.

초기화 실패는 부분적으로 생성한 루트와 파일 상태 보고를 보존합니다. 쓰기 실패는 staging과 관찰된
산출물을 보존하며 루트가 있으면 `recovery-required`를 고정하고 일반 변경을 비활성화합니다. 실패
결과는 동작 단계와 교체를 시도했는지·반환됐는지를 구분합니다. rename 시도 뒤의 `committed: false`는
소스가 그대로라는 증거가 아닙니다. 소스 다시 읽기에 성공했지만 완료 journal 기록에 실패했다면
마지막으로 확인한 after 관찰을 보존하고 전체 실패를 보고합니다. 불확실한 세션을 무작정 복구하거나
재시도하지 마세요.

`result()`는 새로운 파일시스템 검사가 아닌 분리된 **과거 메타데이터**를 반환합니다. 소스 관찰은
명시적으로 `last-confirmed-not-refreshed-by-result`입니다. 모든 결과에 `execution_status: not-run`,
`authorization_status: unknown`, `verified_fix: false`를 유지합니다. 비공개 파일 전이는 취약점을
재현하거나 회귀 테스트를 통과하거나 수정된 앱을 입증하지 않습니다. `close()`는 소유한 descriptor를
닫고 모든 파일을 보존합니다. 종료된 live 상태와 확인된 descriptor 정리는 별도 필드입니다.
불확실한 종료는 정리가 확인됐다고 주장하지 않고 보고합니다.

## 검증과 남은 조건

테스트는 직접 관리하는 비활성 임시 파일, 합성 제안, 모의 clock과 주입한 I/O 실패를 사용합니다.
소스·테스트 바이트에는 의도적으로 최상위 예외를 포함하며 import·수집·실행하지 않습니다. 오프라인
구현 근거이며 실제 사용자 프로젝트 실행이나 설치형 실제 수용이 아닙니다.

다음은 별도의 외부 테스트 interface·runtime과 사람이 검토한 독립 before/after 사례입니다. 이후
CLI 조작 흐름, 현재 설치형 외부 수용, 명시적인 원본 프로젝트 최종 수정과 GUI 연동을 진행합니다.
#152·#150은 열어 두며 S2 전달은 버전·태그, 위험 수용 또는 릴리스 권한을 부여하지 않습니다. 원본의
생성 테스트 경로 부재는 여전히 검사하지 않았으며 원본의 최종 테스트·소스 배치에는 이후의 별도 현재
상태 설계와 결정이 필요합니다.
