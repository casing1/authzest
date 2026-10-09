<p align="center">
  <a href="../../../reference/OWNER_POLICY_CHECK.md">English</a> ·
  <strong>한국어</strong>
</p>

# 고정 소유 정책 검사 API

[문서 목차](../INDEX.md) · [오프라인 사례 계획 계약](OWNER_CASE_PLAN.md) ·
[소유 정책 검토](../guides/CODEX_OWNER_REVIEW.md) · [개발 계획](../development/DEVELOPMENT_PLAN.md)

## 범위와 현재 상태

[#80](https://github.com/casing1/authzest/issues/80)은 유지하는 직접 소유 순수 정책 하나를 위한
소스 전용 API를 `authzest.runner.owner_policy_check`에 추가합니다. 미출시 진행 작업이며
일반 저장소 executor·새 CLI 명령이나 공개 alpha.3 기능이 아닙니다. Windows·frozen 실행 파일은
명시적으로 unsupported/not-run을 반환하고 worker 경로는 지원하는 POSIX Python 소스 설치로
제한합니다.

관리자는 2026-10-09 KST에 #77의 canonical 내용 SHA-256
`7d6296c07ec57b57b217a6fc03bd6fa48304cfe475c1adaf9dbd1d9b285ea598`에 담긴 예상값
10개만 승인했습니다. `owner-read`·`exact-padded-owner`는 허용, 나머지 8개는 거절입니다.
별도 [검토 기록](../../../../tests/fixtures/owner_case_review/maintainer_review.json)은 assistant가
명시적인 채팅 결정을 옮긴 기록이며 인증 여부는 false입니다. 원래 모델 작성 이력을 보존하고
별도 개발 정답 28개·고정 평가셋을 승인하지 않습니다. 예상값만의 결정은 정책 실행 권한이 아닙니다.
같은 날 이후 정확한 소스 검사에 대한 새 별도 승인을 받아 한 번 실행했습니다. 제한된 관찰은 아래에
원래 초안·오프라인 계획과 구분하여 기록합니다.

## 별도 검사 계획과 세션

`prepare_owner_policy_check(offline_plan, labels, case_set, draft, request)`는 제공한 모든
산출물과 정확한 연결을 재검증해 `OwnerPolicyCheckPlan`을 만듭니다. 유지하는 정책 바이트·
등록된 worker·recipe 식별값, 선택한 정답·사례 입력과 고정 한도를 연결합니다. #77의 오프라인
계획 자체는 계속 실행 불가입니다.

`OwnerPolicyCheckSession`은 같은 완전한 맥락으로 불변 계획을 소유합니다.
`decide(choice, plan_id=..., lifetime_seconds=...)`는 별도의 메모리 내 선택을 기록합니다.
선택은 `pending`·`approved`·`declined`·`cancelled`이며 승인에는 정확한 계획 ID와 최대
300초의 유효 기간이 필요합니다. 호출자가 기록한 선택이지 인증된 승인 증표·사람이 결정했다는
증명이나 다른 계획의 동의가 아닙니다. 소스 공유·패치 권한도 부여하지 않습니다.

`await session.run(...)`은 동일한 현재 산출물 맥락을 요구하고 실행 전에 요청·초안·사례 세트·
정답·오프라인 계획·소스·worker·recipe를 재검증합니다. 사전 조건 실패를 포함해 첫 await 전에
세션을 1회용으로 소비합니다. 미검토·거절·취소·만료·변경·재사용 세션은 실행할 수 없습니다.
무효화한 결정을 기존 세션 재사용으로 되살릴 수 없으며 새 정확한 계획과 새 결정을 받아야 합니다.

해시·불변 wrapper는 관련 변경을 감지하지만 신원 증명·승인 서비스나 Python 프로세스를 의도적으로
통제하는 호출자에 대한 보호가 아닙니다. 동시의 적대적 동일 사용자 변경이나 손상된 interpreter·
toolchain을 격리하지 않습니다.

## 고정 worker와 한도

등록된 내장 `policy.py` 소스만 대상입니다. 경로·명령·생성한 Python·shell 입력은 없습니다.
worker는 검증한 사례 데이터를 고정 정책의 dataclass로 해석합니다. scope 배열은 frozenset으로
대응하며 식별값을 trim하거나 정규화하지 않습니다. 모델 이유·검토 의견은 표시 전용 데이터로
유지하고 worker stdin에 보내지 않습니다. FastAPI 예제를 import하거나 서버로 실행하지 않습니다.
HTTP/인증/DB 동작·임의 대상 코드·설치 hook·제공자 호출·패치 적용은 이 API 범위 밖입니다.

| 경계                          | 고정 한도        |
| ----------------------------- | ---------------- |
| 사례 / principal당 scope      | 16 / 16          |
| 식별값 길이                   | 128자            |
| UTF-8 worker 입력 / 출력      | 256 KiB / 16 KiB |
| 자식 프로세스 시작과 I/O 기한 | 5초              |
| kill/reap 정리 예산           | 추가 1초         |
| 결정 유효 기간                | 최대 300초       |

worker는 shell·모델이 선택한 인자 없이 고정 최소 환경과 임시 작업 디렉터리를 사용합니다.
제한된 프로세스 제어이지 OS/네트워크 sandbox·container나 임의 코드의 안전성 증명이 아닙니다.
API에는 의도적인 네트워크 경로가 없으나 신뢰하는 interpreter를 네트워크·다른 host 자원에서
격리한다고 주장하지 않습니다.

## 관찰과 실패를 구분하는 결과

각 사례는 검토한 `expected`와 관찰한 boolean 또는 null인 `observed`를 유지합니다. 비교는
`passed`·`failed`·`unknown`, 전체 결과는 `passed`·`failed`·`not-run`입니다. 누락·잘못된 형식·
미지원·취소·실패 관찰은 null/unknown을 유지하며 거절값이나 보안 통과를 만들어내지 않습니다.
비교 불일치는 관찰 자체가 불가능한 상태와 다릅니다. timeout·출력·worker·사전 조건 실패에서
재시도·대체 worker·모델 호출을 하지 않습니다.

모든 결과는 인가 unknown·제공자 호출 0·패치 적용 not-run을 유지합니다. 순수 정책 비교는 실제
인증·FastAPI 의존성 동작·DB 접근·endpoint 인가를 증명하지 않습니다. 올바른 정책은 수정이
필요하지 않아도 됩니다.

## 2026-10-09 KST의 실제 소스 인수 검증

정확한 고정 정책 검사 1회에 대한 새 별도 승인을 받은 뒤 assistant가 macOS arm64,
Python `3.12.7`의 POSIX 소스 설치에서 해당 검사를 실행했습니다. 검사 계획 ID는
`owner-policy-check-387aeb1740773dc8b05a8570685e73e4ab52df489ce41bd1664f29cf6fb71119`,
등록된 worker SHA-256은
`7a3ac77d65c7a0fd16ac0dbb2cf64bcff0843737027c6ce4e805acf3bf236496`입니다.
별도 [관찰 기록](../../../../tests/fixtures/owner_case_review/observed_check.json)에 공개 worker
출력·한도·현재 host 식별값을 보존합니다. assistant가 기록한 관찰이며 인증된 승인 증표나
독립 실행 증명이 아닙니다.

예상값/관찰값 10개가 모두 일치했습니다. `owner-read`·`exact-padded-owner`는 허용,
나머지 8개는 거절입니다. 전체 상태 `passed`, 자식 종료 `0`, 정리 완료를 확인했습니다.
제공자 호출은 0, 인가는 `unknown`, 패치 적용은 `not-run`입니다. 보존한 정확한 공개 모델 작성
사례를 감싸는 검증된 control-plane 초안을 고정 응답으로 재구성했으며 새 AI 답변이 아닙니다.
모델·제공자 호출이나 새 소스 공유 없이 검사했고 원래 모델 작성 이력을 바꾸지 않았습니다.

별도로 승인한 1회 실행은 소비되었습니다. 앞으로의 실행이나 Windows·frozen 바이너리·HTTP/
인증/DB 동작·임의 정책 입력·별도 개발 정답 행렬 28개로 범위를 넓히지 않습니다. #77 오프라인
계획과 예상값만의 검토 기록은 실행 불가/not-run을 유지합니다. #80은 최종 head CI·리뷰 gate가
통과할 때까지 진행 중입니다. 발행한 것은 없으며 더 넓은 #35 흐름도 완료하지 않았습니다.

## 여전히 필요한 수용 절차

오프라인 계약·프로세스 mock 테스트로 실제 정책을 실행하지 않고 준비·정확한 연결·거절·만료·
1회 사용·한도·실패 기록을 검증할 수 있습니다. 예상값만의 관리자 승인을 실행 동의로 소비하지
않습니다. 추가 실제 관찰에는 별도로 검토한 현재 검사 계획과 새 범위 제한 실행 결정이 필요합니다.
최종 head CI·리뷰, 추가 지원 플랫폼 근거와 이후 #81/#82 수정·통합 수용은 별도의 gate입니다.
이번 작업은 릴리스를 발행하지 않습니다.
