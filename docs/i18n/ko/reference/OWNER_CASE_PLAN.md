<p align="center">
  <a href="../../../reference/OWNER_CASE_PLAN.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 소유 사례 검토와 고정 계획 계약

[문서 목차](../INDEX.md) · [소유 정책 검토](../guides/CODEX_OWNER_REVIEW.md) ·
[개발 계획](../development/DEVELOPMENT_PLAN.md)

## 범위와 제공 상태

[#77](https://github.com/casing1/authzest/issues/77)은 미출시 소스의
`authzest.codex.owner_case_plan`에 스키마 `1.0`의 순수 Python 데이터 API를 추가합니다.
새 CLI 명령이나 executor는 없습니다. 발행한 alpha.3 산출물·패키지 버전 `0.1.0a3`·scan 스키마
`1.2`·제공자·fixture 허용 목록은 유지합니다. 관리자는 2026-10-09 KST에 기록된 정확한 예상값
10개를 명시적으로 승인했습니다. `owner-read`·`exact-padded-owner`는 허용, 나머지 8개는
거절입니다. 별도 [검토 기록](../../../../tests/fixtures/owner_case_review/maintainer_review.json)은
예상값만의 채팅 결정을 보존하며 모델 작성 이력을 바꾸거나 인증된 승인을 주장하지 않습니다.
구현·테스트 자체가 정답을 승인하거나 사례를 실행하거나 모델을 호출하지는 않습니다.

기존 패키지 내 소유 정책 요청·초안만 받으며 제공된 메모리 산출물로 동작합니다. 경로·계정·자격
증명 읽기, 정책 import·평가, 프로세스 시작, 네트워크 연결이나 파일 변경을 하지 않습니다.
FastAPI 예제를 import하거나 서버로 실행하지 않습니다. 모델 이유와 검토 의견은 Python·shell
지시가 아닌 비신뢰 표시 데이터로 유지합니다.

## 사례 묶음과 작성 이력

`prepare_owner_case_set(draft, request, origin=None)`은 기존 계약으로 요청과 소유 정책 결과를
재검증합니다. `OwnerCaseSet`은 정확한 사례 입력·모델 제안 boolean·이유·근거 참조·모델 작성
이력을 보존하고 요청/초안/소스 식별값·두 소스 해시·정책 근거·모델 식별값·프롬프트/출력 스키마
해시를 연결합니다. 사례 1–16개와 공통 UTF-8 256 KiB·깊이 32·노드 8,192개 한도는 새 전체
산출물에도 적용합니다.

선택적 origin은 `code_head`(소문자 16진수 40자 또는 null)와 `date`(유효 ISO 날짜 또는 null)만
받습니다. 호출자가 선언한 출처이며 항상 `authenticated: false`입니다. 해당 커밋에서 모델을
실행했거나 실제 응답 모델을 증명하지 않습니다. 테스트 fixture
`tests/fixtures/owner_case_review/proposed_review.json`은 #77의 공개 10개 사례 전체와 SHA-256
`7d6296c07ec57b57b217a6fc03bd6fa48304cfe475c1adaf9dbd1d9b285ea598`를 변경 없이 보존합니다.
테스트 답변·검토 결정은 명시적인 고정 응답이며 새 제공자 출력이나 사용자 승인이 아닙니다.

## 정확한 예상값 결정

`review_owner_cases(case_set, draft, request, decisions=..., reviewer=None)`는 알려진 사례 ID에
묶인 선택을 기록합니다. 제공한 선택은 `decision`·`expected`·`reason`만 가지며 생략한 ID는
미검토입니다. 미검토 외 이유는 비어 있지 않은 제한된 텍스트이고 미검토 이유는 null입니다.

| 결정       | 선택한 예상값                        | 계획 준비 상태              |
| ---------- | ------------------------------------ | --------------------------- |
| `pending`  | null; 원래 제안은 미검토             | `blocked-pending`           |
| `declined` | null; 선택한 정답 없음               | `blocked-declined`          |
| `approved` | 변환 없이 원래 boolean과 정확히 같음 | 모든 사례를 검토해야 준비됨 |
| `changed`  | 다른 boolean을 별도로 기록           | 모든 사례를 검토해야 준비됨 |

변경한 예상값은 모델 입력·원래 예상값·이유·작성 이력을 덮어쓰지 않습니다. 전체 상태 우선순위는
거절·미검토·변경·승인입니다. 모든 사례가 승인 또는 변경이어야 `all_labels_reviewed: true`입니다.
선택적 검토자 이름은 호출자 텍스트이며 `reviewer_authenticated`는 항상 false입니다. 인증한
승인 증표나 독립적인 의미 검토 증명이 아닙니다. 별도 2026-10-09 관리자 기록은 위의 변경하지
않은 내용 해시에만 적용됩니다. 실행·소스 공유·패치 권한이나 별도 assistant 작성 개발 정답
28개·고정 평가셋의 승인이 아닙니다.

## 고정 계획이며 실행은 아님

`prepare_owner_policy_plan(review, case_set, draft, request)`는 정확한 내장 `policy.py` 바이트,
원래 사례·별도로 선택한 정답·모든 산출물 식별값·버전 있는 고정 harness recipe와 해시를 담은
검토 가능한 `OwnerPolicyPlan`을 만듭니다. 미검토·거절 사례는 차단 미리보기이며 모두 호출자가
검토한 경우 `reviewed-preview`입니다.

어느 계획도 `execution_available: false`, `requires_separate_execution_approval: true`,
`execution_status: not-run`, `authorization_status: unknown`을 바꾸지 않고 패치 적용·제공자
호출도 없습니다. 내용 식별값은 공유·적용·실행 권한이 아닙니다. 제안한 한도(사례 16개·scope
16개·식별값 128자·입력 256 KiB·출력 16 KiB·5초)는 **설계 데이터**이지 실제로 강제한
프로세스/sandbox 보장이 아닙니다. 이 오프라인 계약 자체는 harness·worker를 실행하거나 관찰
결과를 만들지 않습니다. 별도 #80 검사 API에는 자체 한도·결과 기록이 있습니다.

진행 중인 [#80](https://github.com/casing1/authzest/issues/80)은 별도 소스 전용
[고정 정책 검사 API](OWNER_POLICY_CHECK.md)를 추가합니다. 정확한 입력/dataclass 대응(scope
배열은 frozenset, 식별값 정규화 없음)을 유지하고 새롭고 독립적인 정확한 계획 실행 승인을
요구합니다. 여기의 오프라인 계획은 계속 실행 불가입니다. 직접 소유한 순수 정책만 대상으로 하고
HTTP/인증/DB·임의 소스/명령·생성 테스트 실행·설치 hook·네트워크·모델 호출은 제외합니다.
예상값만의 결정은 실행 권한이 아닙니다. 이후 새 별도 승인을 받은 정확한 #80 소스 검사에서
[관찰 10개가 예상값과 일치했습니다](OWNER_POLICY_CHECK.md#2026-10-09-kst의-실제-소스-인수-검증).
순수 정책 결과도 인증이나 endpoint
인가를 입증하지 않습니다. 올바른 정책은 변경이 없어도 됩니다.

## 검증과 불변 snapshot

세 frozen JSON wrapper는 분리된 dictionary를 반환합니다. 직접 생성·호출자 상태·해시는
신뢰 경계가 아닙니다. 제공한 직렬화 산출물에는 완전한 현재 맥락과 함께
`validate_owner_case_set`·`validate_owner_case_review`·`validate_owner_policy_plan`을 사용하세요.
기대하는 host 메타데이터를 재생성하여 중복/누락/순서 변경 결정·알 수 없는 필드·잘못된 정답/근거·
변경한 소스/모델/사례·과거 연결·위조한 상태/recipe를 거절합니다. 입력·원래 예상값·이유·근거·
소스가 바뀌면 이전 정답 검토는 무효입니다. 검토 정답/의견·recipe/한도를 바꾸면 계획 식별값이
바뀌고 이전 미리보기를 거절합니다. 호출자가 의도적으로 결정을 다시 기록하는 것을 막는 API가
아니며 신원 인증·결정 소비·만료·실행 동의를 이 데이터 계약에서 추론하면 안 됩니다.

## Python API와 오프라인 검사

이미 검증한 `draft`와 정확한 패키지 내 `request`가 있다고 가정합니다. 이 예제는 미검토 기록만
만들며 승인 예제가 아니고 실제 계정에서 초안을 받지 않습니다.

```python
from authzest.codex.owner_case_plan import (
    prepare_owner_case_set,
    prepare_owner_policy_plan,
    review_owner_cases,
    validate_owner_policy_plan,
)

case_set = prepare_owner_case_set(draft, request)
labels = review_owner_cases(case_set, draft, request, decisions={})
plan = prepare_owner_policy_plan(labels, case_set, draft, request)
assert plan.to_dict()["planning_status"] == "blocked-pending"
assert plan.to_dict()["execution_available"] is False
validate_owner_policy_plan(plan.payload_json, labels, case_set, draft, request)
```

```bash
python -m pytest tests/test_owner_case_plan.py
```

테스트는 계약 동작 중 파일시스템·제공자·프로세스·네트워크·대상 import를 차단합니다.
정확한 공개 내용을 보존하고 과거/잘못된/위조 입력과 모든 결정 상태를 검증합니다. 오프라인 계약
근거이지 실제 정답 승인·런타임 결과·모델 품질 점수·사용자 설치·릴리스 인수 검증이 아닙니다.
