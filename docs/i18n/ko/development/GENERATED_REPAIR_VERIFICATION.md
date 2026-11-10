<p align="center">
  <a href="../../../development/GENERATED_REPAIR_VERIFICATION.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 검증 — 오프라인 기반

[문서 목차](../INDEX.md) · [생성 계약](GENERATED_REPAIR_CONTRACT.md)

## 상태와 범위 — 2026-11-09 KST

이는 [#150](https://github.com/casing1/authzest/issues/150) 아래
[#152](https://github.com/casing1/authzest/issues/152)의 첫 오프라인 구현 단계입니다.
유지관리자는 로컬 Docker 설계와 관리형 대조군 17개 사례 / 21개 요청을 **오프라인 구현**
범위로 수용했습니다. 이미지 준비, 컨테이너 시작, 생성 코드 실행을 허용한 것은 아닙니다.

소스 API는 내용에 결합된 검증 미리보기, 관리형 대조군 정의, 데이터 전용 비교,
비활성 executor 경계를 제공합니다. 세션·복사본 생성, 앱 파일 읽기, 파일 쓰기·적용·복구,
Codex·worker 시작, 새 CLI 옵션은 제공하지 않습니다. 런타임 이미지, 엔진 어댑터,
실행 가능한 컨테이너 recipe도 추가하지 않습니다. #152는 열린 상태이며 실제 결함 재현이나
검증된 수정을 입증하지 않습니다.

후속 [비공개 파일 기반](GENERATED_REPAIR_WORKSPACE.md)은 오프라인 파일시스템 테스트용으로
분리한 저수준 I/O 도우미입니다. 이 순수 미리보기 API를 바꾸거나 기본 executor를 활성화하지
않습니다. 운영 흐름에 연결하려면 활성 결정·세션 조정기와 실제 캡처 바이트 검사가 여전히 필요합니다.

원래 생성 소스·프롬프트와 `pending-maintainer-review` 정책 메타데이터는 변경하지 않습니다.
별도 대조군 검토 표기는 `maintainer-accepted-offline-design`입니다. 이는 이번 오프라인 검증
설계 수용을 기록할 뿐 생성 프롬프트 변경, 검토자의 독립 인증, 운영 승인, 런타임 관찰을
뜻하지 않습니다. 제품·리포트 버전, 기존 등록 정책 worker와 등록 파일 흐름도 그대로입니다.

## 순수 미리보기 API

[검증 모듈](../../../../src/authzest/runner/generated_repair_verification.py)은 다음을 제공합니다.

- `build_generated_repair_verification_preview(request, proposal)`는 현재 고정 요청·제안을
  재검증하고 분리된 검증 미리보기를 계산합니다.
- `validate_generated_repair_verification_preview(raw, request, proposal)`는 신뢰하지 않는
  직렬화 미리보기를 해당 현재 입력과 유지하는 정의에 대조합니다.

불변 래퍼는 `GeneratedRepairVerificationPreview`, `kind`는
`generated-repair-verification-preview`이며 `verification_preview_id`가 전체 payload를 결합합니다.

미리보기는 전체 비활성 제안, 호스트 계산 앱·테스트 diff와 해시, 관리형 대조군,
고정된 격리 recipe·예산 제안을 결합합니다. 해시 불일치, 예상값·예산 변경, 필드 추가·누락이
계획을 조용히 바꾸도록 허용하지 않습니다. `proposed-change`만 계획된 생성 파일을
설명할 수 있으며 다른 제안 결과를 복사·실행 요청으로 바꾸지 않습니다.

`execution_boundary`는 `unimplemented`이며 오프라인 전용 미리보기입니다. 복사본·파일 부재는
계획이지 파일시스템 관찰이 아닙니다. 적용, 테스트 실체화, 실행, 복구는 미실행이며 권한 보장은
unknown으로 유지합니다. 실제 이미지 ID, 검사한 엔진 기능, 현재 파일 스냅샷, 실제 결정,
수용된 런타임 기록은 없습니다. 해시는 내용을 결합할 뿐 제공자 작성 사실, 호출자 권한,
최신성, 실행 동의를 입증하지 않습니다.

executor 경계는 준비 전용입니다. `GeneratedRepairVerificationExecutor.prepare(preview)`는
`GeneratedRepairExecutorReadiness`를 반환하며 의도적으로 `run`·`execute` 메서드가 없습니다.
`DisabledGeneratedRepairExecutor.prepare`는 `not-ready` / `runtime-not-implemented`로 보고합니다.
`prepare_generated_repair_executor(preview, executor=None)`는 전체 미리보기를 재검증하고
런타임 호출·효과 발생·실행 준비 완료를 주장하는 readiness를 거부합니다. 호출자가 주입한
readiness 구현은 신뢰하는 테스트 경계이지 sandbox나 capability가 아닙니다. 제품 코드는 실제
런타임 어댑터를 선택하거나 호출하지 않습니다. 미리보기 전달은 승인이 아니며 Docker를
시작할 수 없습니다.

## 관리형 대조군

[대조군 모듈](../../../../src/authzest/runner/generated_repair_controls.py)은 고정 정의, 검증,
데이터 전용 비교기를 관리합니다. 예상값은 호스트가 관리하는 데이터이며 생성된 assertion이나
앱·relay·모델 응답이 정하는 값이 아닙니다.

`build_generated_repair_controls()`는 `GeneratedRepairControls`를 반환하고,
`validate_generated_repair_controls(raw)`는 완전한 현재 정의만 수용합니다.
`compare_generated_repair_observations(raw, controls, candidate="before" | "after")`는
명시적 후보와 전체 순서의 사실을 요구합니다. 사실 JSON은 schema `1.0`, kind
`generated-repair-http-facts`, 정확한 `controls_id`, candidate, facts를 가지며 각 사실은
`request_id`, 정수 `status_code`, 헤더 쌍, 정규 `body_base64`만 포함합니다. 이는 제한된 데이터
형식이지 실제 세션의 공개 launcher나 import·재개 옵션이 아닙니다.

| 그룹           | 사례 / 요청 | 수정 후 예상 동작                                                                                      |
| -------------- | ----------- | ------------------------------------------------------------------------------------------------------ |
| 소유자         | 2 / 2       | `alice` / `doc-alice`, `bob` / `doc-bob`: 200, 원래 id·owner·body와 정확히 일치                        |
| 다른 소유자    | 2 / 2       | 양방향 403, 정확한 JSON `{"detail":"Forbidden"}`, 제한된 응답 헤더·본문에 알려진 보호 평문 표식 없음   |
| actor 누락     | 3 / 3       | 두 기존 문서 ID와 고정된 없는 ID: 401, 정확한 JSON `{"detail":"Unknown demo actor"}`                   |
| 빈 actor       | 3 / 3       | 같은 문서 ID 3개: 401, 동일한 정확한 오류 본문                                                         |
| 미등록 actor   | 3 / 3       | 고정 `mallory` actor, 같은 문서 ID 3개: 401, 동일한 정확한 오류 본문                                   |
| 없는 문서      | 2 / 2       | 각 유효 actor가 고정된 없는 문서를 요청하면 404, 정확한 JSON `{"detail":"Document not found"}`         |
| 정상 사용 순서 | 2 / 6       | 각 actor의 자기 문서 읽기 → 타인 문서 요청 → 자기 문서 다시 읽기: 200 / 403 / 200, 원래 성공 응답 유지 |
| 합계           | 17 / 21     | 계획된 정의이며 관찰한 사례·HTTP 횟수가 아님                                                           |

before 기준은 원하는 수정 후 기준과 다릅니다. 소유자·잘못된 actor·없는 문서 동작은
유지되지만 각 타인 문서 요청은 알려진 합성 문서 전체를 노출하는 의도된 누락을 확인해야
합니다. import 실패, timeout, 무관한 assertion 실패, 일반적인 테스트 실패는 해당 누락을
재현한 것이 아닙니다. after는 두 정상 사용 순서를 포함한 전체 대조군을 요구하며 일부만
골라 통과시켜서는 수정 검증이 되지 않습니다.

평문 노출 검사는 알려진 유한한 표식만 확인합니다. 모든 인코딩, 은닉 채널, 변형된 노출,
이 요청 바깥의 동작까지 찾는 것은 아닙니다. 호출자가 선택하는 `X-Demo-Actor`는 fixture
데이터이며 인증이나 신뢰할 수 있는 신원이 아닙니다.

### 데이터 비교는 런타임 근거가 아님

비교기는 전달받은 제한된 응답 사실을 관리형 예상값과 비교합니다. HTTP를 요청하지 않으며
생성 소스·테스트를 import하거나 실행하지 않습니다. 누락·중복·순서 변경·잘못된 형식·미지원
사실을 완전한 일치 관찰로 세어서는 안 됩니다. 일치는 **전달한 데이터가 기준과 일치함**만
뜻합니다. 출처, 앱 실행 여부, 실행한 파일 바이트, 격리·정리 성공, 수정 정확성을 입증하지
않습니다.

비교 결과는 `status: "data-only"`, `comparison_status`는 `matches-expected-profile` 또는
`profile-mismatch`이며 `provenance: "caller-supplied-unverified"`를 보존합니다.
`execution_status: "not-established"`, `verified_fix: false`도 명시합니다. 횟수는 전달받은
데이터의 비교 횟수이지 독립적으로 관찰한 요청 성공 횟수가 아닙니다.

향후 활성 흐름은 검토한 relay 경계로 완전한 사실을 별도 수집하고 실제 파일·런타임
식별자와 결합하며 capture·정리 근거를 보존해야 합니다. 생성 pytest 보고는 신뢰하지 않는
보조 정보입니다. 생성 Python은 자체 실패·통과 보고를 위조할 수 있으며 호스트가 비교하는
관리형 대조군을 대신할 수 없습니다.

## 제안한 격리 경계 — 미구현

수용한 방향은 선택적이고 신뢰하는 로컬 Linux Docker 엔진입니다. 생성 pytest의 호스트 실행이나
등록 정책 worker의 허용 범위 확대가 아닙니다. 각 before/after 단계는 새 역할을 사용합니다.

- **T — 생성 테스트:** 정확히 capture한 앱·테스트 바이트, 고정 pytest 진입점, network none.
- **A — 앱:** 정확히 capture한 앱 바이트, 생성 테스트 없음, 고정 이미지 소유 ASGI 서버,
  network none과 고정 컨테이너 내부 loopback 포트.
- **B — 관리형 relay:** 별도 PID·파일시스템 namespace, 소스·테스트 mount 없음.
  A의 정확한 네트워크 namespace에만 합류해 고정 요청을 보내고 제한된 응답 사실을 반환.
- **호스트 oracle:** 생성 Python과 guest 밖에서 예상값과 최종 판정을 관리.

T와 A/B는 분리 실행하므로 생성 테스트 상태가 관리형 대조군 실행에 이어지지 않습니다.
제안한 guest recipe는 고정 non-root 신원, 읽기 전용 root, capability 제거,
no-new-privileges, seccomp와 실제 CPU·메모리·PID·tmpfs 제한을 요구합니다. 정확한 읽기 전용
staging 입력 파일만 mount할 수 있습니다. 원본 체크아웃·HOME·자격정보·결과 journal·Docker
socket mount, 호스트 환경 상속, 호스트 포트, bridge·외부 네트워크, 모델이 고른 명령·의존성은
없습니다. 검사 중 암묵적인 이미지 pull·build·의존성 설치도 금지합니다. 이는 제안 요구사항이지
이번 소스가 검사·강제한 기능은 아닙니다.

신뢰하는 OS·엔진·검토한 이미지/의존성·운영자는 경계에 포함됩니다. 컨테이너는 탈출 불가능한
격리가 아니며 손상된 엔진·커널이나 모든 동일 사용자 동시 공격자를 방어하지 않습니다.
로컬 엔진과 이미지의 실현 가능성은 미검증입니다. scan·오프라인 미리보기는 Docker가 필요 없고
위험한 호스트 실행 fallback도 계획하지 않습니다.

### 후속 예산

미리보기는 아래 제안 상한을 결합합니다. 미리보기·비교기 자체는 timer, 자원 controller,
실제 결정을 구현하지 않습니다.

| 자원                 | 제안 상한                                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| 각 단계 로컬 결정    | 원래 최대 300초, 1회 사용, 갱신·재사용·재개 없음                                                  |
| 각 before/after 검사 | T 다음 A/B까지 공유하는 setup·capture 40초, 그 안의 누적 readiness 최대 10초, 정리 추가 최대 10초 |
| T 또는 A             | CPU 1개, 메모리 512 MiB, swap 상한=메모리, PID 64개, tmpfs 32 MiB                                 |
| B                    | CPU 0.5개, 메모리 128 MiB, swap 상한=메모리, PID 32개, tmpfs 8 MiB                                |
| 공유 메모리          | guest마다 최대 8 MiB                                                                              |
| HTTP 사실            | 응답마다 상태줄 512바이트, 헤더 32개 / 헤더 블록 4 KiB, 본문 8 KiB                                |
| 프로세스 출력        | 해당 단계 전체 역할의 stdout·stderr 합계 256 KiB, 수집 중 제한                                    |
| 보존할 세션 데이터   | 기록·산출물 합계 2 MiB                                                                            |

기존 소스·테스트별 16,384바이트와 파싱 전용 AST 예산은 그대로입니다. 역할·요청이 바뀌어도
단계 시간이 재시작되지 않으며 readiness는 추가 실행 시간이 아닙니다. timeout, OOM, 잘림,
잘못된 데이터, 불완전 capture, 저장 실패, 정리 미확인은 서로 다른 실패로 남겨야 합니다.
파일시스템·daemon·kernel 작업의 보편적 절대 시간 보장은 없습니다. 향후 활성 수용은 flag를
믿는 대신 실제 제한 적용을 측정해야 합니다.

## 후속 복사본·복구 의미

이번 단계는 복사본을 만들거나 소스·테스트를 쓰지 않습니다. 의도한 순서는
복사 → before 검사 → 소스 diff 수용 → 소스 적용 → after 검사 → 복구이며 각각 현재
내용·파일·선행 결과에 결합된 별도 결정과 실패 상태를 갖습니다.

후속 복사본 생성은 고정 before `app.py`와 `tests/test_generated_ownership.py` 실체화를
새 비공개 복사본에 명시적으로 승인해야 합니다. 부재 예정 테스트는 독점 생성·readback 전에
실제 부재를 확인해야 합니다. 테스트는 PoC 실행 **이전**에 생성하며 after 앱 소스는 적용하지
않습니다. 이후 소스 적용은 정확한 앱 대체 diff만 사용하며 앱·테스트의 원자적 동시 패치가
아닙니다.

복사 시점 복구 대상은 **생성 테스트를 그대로 보존하는** 정확한 before 앱 바이트와 근거입니다.
복구는 테스트가 없던 원래 트리를 재현하거나 산출물을 삭제하지 않습니다. 원본 체크아웃은
쓰기 대상이나 런타임 mount가 될 수 없습니다. 후속 파일 작업은 symlink·hardlink·신원 교체,
오래되거나 누락·사용자 편집한 파일, 불확실한 상태를 덮어쓰지 않고 거부해야 합니다.
단일 파일 atomic rename은 동일 사용자 compare-and-swap 보장이 아니며 부분 초기화나
fsync·journal 실패를 쓰기 없음으로 표시해서는 안 됩니다.

정리는 정확한 세션 소유 guest만 식별하고 종료·제거를 확인하며 제한된 근거를 보존해야 합니다.
정리 불명, 변경된 파일, 교체 상태 불확실은 강제 복구가 아닌 점검·recovery-required 상태입니다.
바이트를 복구해도 실패한 수정 검사를 성공으로 바꿀 수 없습니다.

## 다음 구현 단계와 gate

1. 전용 비공개 복사본·세션 상태 계약과 임시 파일 기반 거부, 정확한 diff, 테스트 실체화,
   복구 회귀를 추가합니다. 기존 등록 worker API는 완화하지 않습니다.
2. mock 엔진·capture 생명주기와 엄격한 relay 사실 경계를 추가합니다. create/start 불확실,
   위조 보고, 순서 변경·초과 사실, 취소, 저장·정리 실패를 다룹니다.
3. 이 경계를 검토한 뒤 명시적 CLI 계획·개별 결정, 이스케이프된 사람용 상태, 버전이 있는
   결과 기록을 추가합니다. 현재 명령은 변경하지 않습니다.
4. 이미지 준비·기능 확인과 설치 후보의 실제 런타임 검증을 별도 검토합니다. 실제 AI 공유,
   생성 실행, 복사·적용·복구, 실제 실행 공개에는 해당 범위가 필요하며 오프라인 테스트나
   수용 표기가 그 권한을 부여하지 않습니다.

오프라인 회귀는 실행하지 않는 소스 텍스트, 전달받은 사실, 비활성·가짜 경계만 사용하며 생성
앱·테스트를 import·compile·수집·실행하지 않아야 합니다. 후속 수용 실행은 정확한 설치 후보,
소스·테스트·diff, 대조군·검토, 검사한 엔진·이미지, 실제 before·after·복구 파일과 완전한
capture·정리 확인을 결합해야 합니다. 현재 미리보기나 비교는 이 gate를 충족하지 않습니다.
읽기 전용 로컬 UI(#153), 배포 준비(#85), 위험 검토와 릴리스는 별도이며 이 기반만으로
어떤 이슈도 완료하지 않습니다.
