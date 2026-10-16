<p align="center">
  <a href="../../../reference/OWNER_POLICY_RECOMMENDATION.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 소유 정책 추천 API

[문서 목차](../INDEX.md) · [개발 계획](../development/DEVELOPMENT_PLAN.md) ·
[원래 S1 설계](../development/OWNER_POLICY_IMPROVEMENT_DESIGN.md) ·
[이슈 #81](https://github.com/casing1/authzest/issues/81)

## 제공 상태와 경계 — 2026-10-16 KST

이 브랜치는 `authzest.codex.owner_policy_recommendation`에 S1의 소스 전용 순수 Python
데이터 API를 구현합니다. 고정 요청·엄격한 추천 검증·검토 가능한 미리보기만 제공합니다.
alpha.3에 발행한 기능·새 CLI 명령·제공자 adapter·AI 생성 패치나 전체 #81 흐름은 아닙니다.
최종 구현 CI·리뷰와 더 넓은 #81/#82 수용은 별도의 gate입니다.

변경하지 않은 [설계](../development/OWNER_POLICY_IMPROVEMENT_DESIGN.md)는 2026-10-15의
과거 제안입니다. 이 구현 시점의 [PR #98](https://github.com/casing1/authzest/pull/98)
`a170d82`는 draft·미병합 상태입니다. 제한된 S1 진행은 전체 #81 확장 승인·해당 설계 PR
병합·모델 호출·정책 실행·패치 권한을 뜻하지 않습니다.
별도 [S1 범위 결정](https://github.com/casing1/authzest/issues/81#issuecomment-6206079101)은
2026-10-16의 진행을 기록하며 이 데이터 객체가 지니는 승인 권한이 아닙니다.

API는 등록된 메모리 상수만 사용합니다. 경로·임의 소스·저장소·모델 선택·callback·사례 묶음·
정답 기록·관찰 기록은 받지 않습니다. 파일시스템·네트워크·제공자·프로세스 접근, 정책 평가/
import·적용·복구를 하지 않습니다. `policy.py`는 열 파일이 아닌 논리적 데이터 이름입니다.
기존 소유 정책 검토/제안 계약·#80 worker/허용 목록·scan 동작·과거 모델/정답/관찰 기록은 그대로입니다.

## Python 진입점

| 진입점                                                                 | 결과                                                                           |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `build_owner_policy_recommendation_request()`                          | 등록된 `OwnerPolicyRecommendationRequest` 생성; 호출자가 고른 소스·설정은 없음 |
| `validate_owner_policy_recommendation_request(raw)`                    | 정확한 현재 요청을 다시 생성·검증                                              |
| `validate_owner_policy_recommendation(raw, request)`                   | 정확한 연결을 가진 `OwnerPolicyRecommendation` 검증                            |
| `prepare_owner_policy_recommendation_preview(recommendation, request)` | 두 산출물을 재검증해 `OwnerPolicyRecommendationPreview` 생성                   |

요청은 `request_id`, 검증된 추천은 `recommendation_id`를 제공합니다. 세 wrapper 모두
분리된 데이터의 `to_dict()`를 제공합니다. 직접 생성한 dataclass·복사한 ID·상태·타입
wrapper는 검증이나 승인 권한이 아닙니다. 제공한 산출물을 완전한 현재 등록 맥락에 대해
재검증해야 하며 변경하거나 위조한 내용은 거절합니다.
validator의 `raw` 인자는 dictionary·경로·실행 입력이 아닌 직렬화한 JSON 텍스트입니다.

## 요청과 원시 추천

요청 스키마 `1.0`은 리포트 스키마 `1.2`·패키지 버전 `0.1.0a3`와 독립적입니다.
`schema_version`·`kind`·`scenario_id`·`source`·`criteria`·`assumptions`·`registry`만
포함합니다. 등록된 `OWNER_POLICY_SOURCE` 바이트는 줄 끝을 유지하고 새 정책 전용 기준
snapshot은 끝에 LF가 없습니다. 고정 순서의 신뢰 입력 가정과 쌍이 없는 registry 버전
`empty-v1`은 host 소유이며 호출자가 덮어쓰지 않습니다.

소스/기준 근거 ID·요청/추천 ID는 [설계](../development/OWNER_POLICY_IMPROVEMENT_DESIGN.md)의
prefix·해시 입력으로 정확한 canonical 내용을 연결합니다. 요청 ID는 자기 참조하는 요청
필드가 아닌 도출 속성입니다. 바이트·버전이 바뀌면 과거 연결은 무효입니다. 해시는 내용을
식별할 뿐 신원이나 동의를 증명하지 않습니다.

원시 추천은 다음 필드만 가집니다.

| 필드               | 규칙                                                            |
| ------------------ | --------------------------------------------------------------- |
| `schema_version`   | 정확히 `1.0`                                                    |
| `request_id`       | 정확한 현재 요청 ID                                             |
| `status`           | 정확히 `no-change` 또는 `unknown`                               |
| `rationale`        | 제한된 비어 있지 않은 텍스트                                    |
| `evidence_ids`     | 서로 다른 등록 소스/기준 ID 모두; 알 수 없거나 중복한 ID는 없음 |
| `assumptions`      | 각 항목이 비어 있지 않은 제한된 텍스트; 최소 1개                |
| `uncertainties`    | 각 항목이 비어 있지 않은 제한된 텍스트; `unknown`이면 최소 1개  |
| `expected_effects` | 각 항목이 비어 있지 않은 제한된 텍스트; 최소 1개                |
| `limitations`      | 각 항목이 비어 있지 않은 제한된 텍스트; 어느 상태든 최소 1개    |
| `change_pair_id`   | 정확히 JSON null                                                |

`no-change`는 이 입력 범위에서 소스 변경을 뒷받침할 근거가 없다는 뜻이지 정책이 안전하다는
판정이 아닙니다. `unknown`은 추천에 필요한 근거의 부족을 기록하며 거절값이나 관찰 실패를
만들어내지 않습니다. 형식/참조 검증으로 의미상 정확성·신뢰하는 인증·endpoint 강제를 입증하지
않습니다. 지시·코드처럼 보이는 텍스트도 데이터로 유지합니다.

비어 있어도 추가 필드는 거절합니다. 사례·정답·관찰·교체 소스·diff/패치/명령/실행 가능한
테스트·제공자/모델 신원 주장·승인 선택·실행/적용 상태는 원시 계약 밖입니다. null이 아닌
모든 변경 쌍 ID는 거절합니다. S1에 registry를 채우는 옵션이나 부정 test-only 변형은 없습니다.

## 미리보기 사실과 한도

출력 전용 미리보기는 분리된 요청/결과 snapshot·각 ID·정확한 소스/기준 해시·registry 버전을
다시 만듭니다. 제출한 미리보기를 승인으로 받지 않습니다. host 소유 사실은 다음과 같습니다.

| 필드                                                            | 값                                                                   |
| --------------------------------------------------------------- | -------------------------------------------------------------------- |
| `changes` / `diffs`                                             | 빈 배열                                                              |
| `provider_calls`                                                | 이 연산에서 `0`                                                      |
| `execution_status` / `patch_application` / `restoration_status` | `not-run`                                                            |
| `authorization_status`                                          | `unknown`                                                            |
| `provenance`                                                    | 정확히 `kind` = `caller-supplied-data`, `authenticated` = JSON false |

이 사실은 실제 모델 출처·인증된 검토 증표·공유/실행 권한이 아닙니다. 미리보기는 renderer나
승인 서비스가 아닌 데이터입니다. 표시할 때 비신뢰 텍스트를 이스케이프하세요. 복사한 snapshot·
Markdown·터미널 제어 문자가 권한을 부여할 수 없습니다.

| 경계                          | 한도                               |
| ----------------------------- | ---------------------------------- |
| 완전한 canonical UTF-8 산출물 | 262,144바이트                      |
| JSON 깊이 / 방문 노드         | 32 / 8,192                         |
| 등록 소스 텍스트              | 32,768자                           |
| 일반 텍스트 항목 / ID         | 4,096 / 128자                      |
| 텍스트 목록                   | 최대 32개 항목; 최솟값은 위와 같음 |
| 근거 ID                       | 서로 다른 등록 ID 정확히 2개       |

요청·추천·snapshot·완전한 host 미리보기와 host 메타데이터 증가 모두에 한도를 적용합니다.
정확한 객체 키/scalar 타입·중복 JSON 키·비유한 숫자·유효하지 않은 Unicode·공통 텍스트 제어
규칙을 변환 없이 확인합니다. 일반 텍스트에 TAB/LF/CR을 허용하며 helper가 모든 bidi/zero-width
문자를 제거하지는 않으므로 안전한 표시가 여전히 필요합니다.

## 명시적인 고정 응답 Python 예제

이 예제는 `unknown`인 **SCRIPTED** 응답을 만듭니다. `no-change`를 추론하거나 AI 답변을
받거나 정책을 평가하거나 무언가를 승인하지 않습니다. JSON 출력은 ASCII 이스케이프한 표시
데이터입니다. alpha.3 실행 파일이 아닌 이 브랜치의 소스 구현이 있는 환경을 사용하세요.

```python
import json

from authzest.codex.owner_policy_recommendation import (
    build_owner_policy_recommendation_request,
    prepare_owner_policy_recommendation_preview,
    validate_owner_policy_recommendation,
    validate_owner_policy_recommendation_request,
)

request = build_owner_policy_recommendation_request()
request = validate_owner_policy_recommendation_request(
    json.dumps(request.to_dict(), ensure_ascii=True)
)
payload = request.to_dict()

# SCRIPTED caller-owned example, not a model response or a policy verdict.
SCRIPTED_RESULT = {
    "schema_version": "1.0",
    "request_id": request.request_id,
    "status": "unknown",
    "rationale": "Scripted example: no semantic review was performed.",
    "evidence_ids": [
        payload["source"]["evidence_id"],
        payload["criteria"]["evidence_id"],
    ],
    "assumptions": ["This is caller-supplied demonstration data."],
    "uncertainties": ["The example does not establish recommendation correctness."],
    "expected_effects": ["No source change or execution is requested."],
    "limitations": ["No provider, policy evaluation or endpoint verification."],
    "change_pair_id": None,
}
recommendation = validate_owner_policy_recommendation(
    json.dumps(SCRIPTED_RESULT, ensure_ascii=True), request
)
preview = prepare_owner_policy_recommendation_preview(recommendation, request)
print(json.dumps(preview.to_dict(), ensure_ascii=True, indent=2))
```

## 검증과 다음 gate

필수 오프라인 검증은 두 결과 상태·분리/위조/과거 산출물·정확한 근거와 고정 필드·한도 경계·
파일시스템/네트워크/제공자/프로세스 효과나 대상 import/평가를 막는 guard를 포함합니다.
이것은 검증 요구사항이지 이 문서가 기록하는 테스트 수나 통과 결과가 아닙니다. 구현 결과는
실제로 수행한 검사로 보고해야 합니다.

S1으로 #81을 완료하지 않습니다. 사례/정답/관찰·제공자 연결·등록 수정 쌍·변경 전후 정책 검사는
별도로 검토한 확장과 정확한 산출물 연결이 필요합니다. 이후 실제 요청에는 새 최소 공유 승인이
필요하고 정확한 diff 적용·검증·복구는 각각 현재 상태에 대한 별도 결정을 요구합니다.
이 데이터 객체를 준비·검증한다고 릴리스·태그·추가 승인이 따라오지 않습니다.
