<p align="center">
  <a href="../../../reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 등록 수정 추천 계약

[문서 목차](../INDEX.md) · [개발 계획](../development/DEVELOPMENT_PLAN.md) ·
[등록 수정 쌍 API](OWNER_POLICY_REPAIR_PAIR.md) ·
[변경 없는 S1 추천 API](OWNER_POLICY_RECOMMENDATION.md) ·
[이슈 #81](https://github.com/casing1/authzest/issues/81)

## 가용성과 경계 — 2026-10-21 KST

이 문서는 #81에서 추적하는 `authzest.codex.owner_policy_repair_recommendation`의
**새 미출시 소스 진행 작업**입니다. 등록된 테스트 전용 수정 쌍을 선택하는 별도 순수 오프라인
계약이며 새 CLI 명령·제공자 adapter·실제 Codex 답변·AI 작성 소스/diff·전체 #81/#35 흐름이
아닙니다. 이 문서는 새 CI·리뷰·전달 결과나 런타임 관찰을 주장하지 않습니다.

고정 수정 쌍 API는 2026-10-21 KST에 [PR #101](https://github.com/casing1/authzest/pull/101)의
병합 `cbe6b37`로 전달됐습니다. 이 확장은 정확히 그 등록 소스·기준·가정·검토한 예상값 8개·검토
기록 연결을 사용합니다. 검토 전문이나 URL을 내장하지 않고 hash로 고정합니다. 작성 이력을 변경하거나 기록된 예상값 결정을 인증된 승인·실행 동의·관찰
결과로 바꾸지 않습니다. 공개 alpha.3, 보고서 스키마 `1.2`, S1 스키마 `1.0` / 레지스트리
`empty-v1`, #80의 올바른 정책 worker는 그대로입니다. 부정 후보를 해당 worker 허용 목록에
추가하지 않습니다.

파일시스템/네트워크/제공자/프로세스 접근·대상 import/평가·파일 적용·복구는 없습니다.
`policy.py`는 입력 경로가 아닌 논리적 표시 이름입니다. 임의 소스·저장소·callback·모델 선택·대체
수정 쌍·사례·예상값·승인을 받지 않습니다. 프롬프트는 비활성 텍스트이며 생성해도 Codex에
아무것도 보내지 않습니다.

## Python 진입점

| 진입점                                                                 | 결과                                                  |
| ---------------------------------------------------------------------- | ----------------------------------------------------- |
| `build_owner_policy_repair_recommendation_request(candidate="before")` | 정확히 `before` 또는 `after`의 고정 요청 구성         |
| `validate_owner_policy_repair_recommendation_request(raw)`             | 전체 정확한 현재 요청을 재구성·검증                   |
| `owner_policy_repair_recommendation_prompt(request)`                   | 요청을 다시 검증하고 고정 프롬프트와 JSON 데이터 합성 |
| `validate_owner_policy_repair_recommendation(raw, request)`            | 정확한 요청에 연결된 닫힌 결과 검증                   |
| `prepare_owner_policy_repair_recommendation_preview(result, request)`  | 두 산출물을 다시 검증하고 출력 전용 미리보기 합성     |

validator는 파일 경로나 실행 입력이 아닌 직렬화한 JSON 텍스트를 받습니다. ID와 wrapper는 승인
권한이 아닙니다. 소비자는 복사한 hash나 직접 만든 dataclass만 믿지 않고 전체 현재 문맥을 다시
검증합니다. 분리된 snapshot으로 새 내용을 등록할 수 없습니다. 버전·후보·프롬프트·등록 내용이
변경되면 이전 연결은 유효하지 않습니다.

## 요청·근거·결과의 의미

이 별도 스키마 `1.0`은 프롬프트·후보·전체 등록 수정 쌍 문맥과 hash를 고정합니다. `before`는
경고를 명시한 의도적 오류의 테스트 전용 소스를, `after`는 변경 없는 올바른 관리 소스를
선택합니다. 두 후보 모두 동일한 전체 등록 수정 쌍을 근거로 유지합니다. 호출자가 선택한 소스
정규화나 편집은 없습니다. 내용 식별값은 정확한 데이터를 연결할 뿐 작성자나 공유 허가를
증명하지 않습니다.

닫힌 요청에는 정확히 다음 필드만 있습니다.

| 필드                      | 연결                                                                           |
| ------------------------- | ------------------------------------------------------------------------------ |
| `schema_version` / `kind` | `1.0` / `owner-policy-repair-recommendation-request`                           |
| `candidate`               | 정확히 `before` 또는 `after`; 기본값 `before`                                  |
| `prompt`                  | 정확히 `version` = `owner-repair-selection-v1`과 고정 `text`                   |
| `registry`                | 정확한 등록 `version`, `pair_id`, `content_sha256`, `review_record_sha256`     |
| `content`                 | 두 소스·기준·가정·사례/예상값을 포함한 전체 정확한 등록 수정 쌍 내용           |
| `evidence_ids`            | 정확히 `before`, `after`, `criteria`, `cases`; 각각 전체 해당 내용 부분에 연결 |

도출한 `request_id`는 자기 참조 요청 필드가 아닙니다. 렌더링 함수는 정확한 고정 지시 텍스트,
`\nREQUEST_JSON:\n`, canonical 요청 JSON, `\nREQUEST_ID:\n`, 도출한 ID, 마지막 LF를
반환합니다. 프롬프트 버전은 지시와 이 렌더링 recipe를 모두 고정하며 선택한 모델이나 제공자
응답을 식별하지 않습니다.

결과는 다음 데이터 상태를 사용합니다.

| 상태                | 허용 연결                                    | 이 계약 범위의 의미                               |
| ------------------- | -------------------------------------------- | ------------------------------------------------- |
| `registered-change` | `before` 요청만; 정확한 현재 등록 수정 쌍 ID | 대체 소스가 아닌 host 등록 변경 하나 선택         |
| `no-change`         | 수정 쌍 ID는 JSON null                       | 변경을 선택하지 않음; 보안 판정은 아님            |
| `unknown`           | 수정 쌍 ID는 JSON null                       | 부족한 근거를 명시적으로 유지; 관찰한 실패는 아님 |

모든 결과는 정확한 등록 근거 ID 4개와 서로 다른 기존 사례 ID 1–8개를 참조합니다. 신규·중복
근거/사례 참조는 거절합니다. 이유·가정·불확실성·예상 효과·한계는 크기를 제한한 신뢰하지 않는
설명 데이터입니다. `unknown`에는 비어 있지 않은 불확실성 목록이 필요합니다. validator는 설명의
진실성을 확인하거나 문자열 내부의 거짓 주장을 막을 수 없습니다. 참조나
`registered-change` 상태가 유효해도 설명의 정확성이나 선택한 변경의 수정 효과는 증명하지 않습니다.

원시 결과에 소스·diff·명령·실행 테스트·사례/정답·관찰·승인 필드를 제공할 수 없습니다. 빈
필드라도 추가 필드는 거절합니다. 결과 JSON에서 제공자/모델 출처와 실행 주장을 받지 않습니다.
설명 문자열의 지시나 코드 같은 텍스트는 신뢰하지 않는 데이터이며 평가하거나 허가로 취급하면
안 됩니다.

원시 결과에는 정확히 `schema_version`, `request_id`, `status`, `rationale`, `evidence_ids`,
`case_ids`, `assumptions`, `uncertainties`, `expected_effects`, `limitations`,
`change_pair_id`가 있습니다. 가정·예상 효과·한계에는 각각 비어 있지 않은 항목이 하나 이상
필요하며 `unknown`에는 불확실성도 하나 이상 필요합니다. 다른 상태의 불확실성 배열은 비어 있을
수 있습니다. 모든 설명 배열은 최대 32개이며 대소문자 변경/형 변환이나 키 생략은 받지 않습니다.

## 출력 전용 미리보기와 다음 gate

유효한 `before` / `registered-change` 결과에만 기존 host가 도출한 정확한 수정 쌍 diff를
`pair_preview`에 합성하며 기존 등록 수정 쌍 미리보기 dictionary 전체를 포함합니다.
`no-change`와 `unknown`은 `pair_preview`를 JSON null로 설정합니다. 합성 미리보기에는
재검증한 `request` / `recommendation`, 각 ID와
`owner-policy-repair-recommendation-preview` kind도 포함합니다. 호출자가 제공하거나 추가한
`changes` / `diffs` 필드는 없습니다. 모든 소스/diff
바이트와 동작 사실은 제출한 응답이 아닌 host가 소유합니다. 제공자 호출은 `0`, 실행·적용·복구는
`not-run`, 전후 관찰은 null, 비교는 `not-evaluated`, 인가는 `unknown`입니다.

미리보기 출처는 인증하지 않은 호출자 제공 데이터입니다. 호출자가 전체 결과를 scripted로 만들
수 있으며 이 API에는 전송 영수증이나 실제 모델 근거가 없습니다. 미리보기는 renderer·공유 동의
기록·실행 계획·패치 서비스가 아닌 데이터입니다. 후속 renderer는 신뢰하지 않는 텍스트를
escape해야 합니다. 프롬프트·diff·복사한 JSON을 출력해도 권한은 생기지 않습니다.

## 크기 제한과 명시적 scripted 예제

전체 canonical/원시 UTF-8 산출물과 렌더링한 프롬프트는 262,144바이트, JSON 깊이는 최대 32,
방문 node는 최대 8,192개입니다. 전체 합성 미리보기 metadata와 중첩된 등록 수정 쌍 미리보기도
제한에 포함합니다. 일반 설명은 4,096자, ID는 128자까지입니다. 공통 decoder는 소스를 묵시적으로
정규화하지 않고 중복 키·유한하지 않은 수·잘못된 Unicode·금지한 텍스트 제어 문자를 거절합니다.
모양이 유효한 대체 프롬프트·소스·정답·검토 hash·근거도 정확한 등록 내용 일치 검증에서 거절합니다.
일반 텍스트는 TAB/LF/CR을 허용하며 모든 bidi/zero-width 문자를 제거하지 않으므로 안전한 표시는
별도 책임입니다.

alpha.3 실행 파일이 아닌 이 새 작업을 포함한 소스 환경을 사용하세요. 이 예제는 명시적
**SCRIPTED** `unknown` 응답을 구성합니다. 제공자를 호출하거나 정책 후보를 평가하거나
아무것도 적용하지 않으며 공유/실행 동의도 부여하지 않습니다. 전체 준비 프롬프트와 출력
미리보기는 ASCII escape한 표시 데이터로 출력합니다.

```python
import json

from authzest.codex.owner_policy_repair_recommendation import (
    build_owner_policy_repair_recommendation_request,
    owner_policy_repair_recommendation_prompt,
    prepare_owner_policy_repair_recommendation_preview,
    validate_owner_policy_repair_recommendation,
    validate_owner_policy_repair_recommendation_request,
)

request = build_owner_policy_repair_recommendation_request(candidate="before")
request = validate_owner_policy_repair_recommendation_request(
    json.dumps(request.to_dict(), ensure_ascii=True)
)
payload = request.to_dict()

# SCRIPTED caller-owned data, not a model answer or policy verdict.
SCRIPTED_RESULT = {
    "schema_version": "1.0",
    "request_id": request.request_id,
    "status": "unknown",
    "rationale": "Scripted example: no semantic review was performed.",
    "evidence_ids": list(payload["evidence_ids"].values()),
    "case_ids": [payload["content"]["cases"][0]["case_id"]],
    "assumptions": ["This is caller-supplied demonstration data."],
    "uncertainties": ["No model answer or before/after observations were obtained."],
    "expected_effects": ["No change selected, policy execution or patch requested."],
    "limitations": ["Reference validation does not establish semantic correctness."],
    "change_pair_id": None,
}
result = validate_owner_policy_repair_recommendation(
    json.dumps(SCRIPTED_RESULT, ensure_ascii=True), request
)
preview = prepare_owner_policy_repair_recommendation_preview(result, request)
print(json.dumps({
    "prepared_prompt": owner_policy_repair_recommendation_prompt(request),
    "preview": preview.to_dict(),
}, ensure_ascii=True, indent=2))
```

## 검증과 남은 gate

오프라인 검증은 두 후보와 모든 상태, 정확한 요청/프롬프트/근거/사례 연결, 과거·위조·분리된
데이터, 닫힌 필드와 전체 산출물 크기 경계, 부작용·정책 import/평가 방지를 다뤄야 합니다.
이는 요구사항이지 여기서 주장하는 결과가 아닙니다.

다음 실제 연동에는 별도 정확한 공유 미리보기·최소화한 전송 검토·새 제한된 공유/제공자 사용
승인이 필요합니다. 고정 프롬프트만으로 전송이나 동의 경계를 제공하지 않습니다. 이후 전후 관찰은
별도 검토한 고정 worker recipe와 새 정확한 계획 결정을 받아야 하며 #80은 부정 소스를 계속
거절해야 합니다. 정확한 diff 승인·새 복사본 적용·검증·복구는 이후 독립적인 현재 상태 결정을
받습니다. 이 데이터 객체는 실제 호출·실행·패치·병합·태그·릴리즈를 허용하지 않습니다. 더 넓은
#81/#82와 프리릴리즈 gate는 열려 있습니다.
