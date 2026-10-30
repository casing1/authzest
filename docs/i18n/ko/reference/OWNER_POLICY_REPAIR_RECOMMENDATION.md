<p align="center">
  <a href="../../../reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md">English</a> ·
  <strong>한국어</strong>
</p>

# 등록 수정 추천과 공유

[문서 목차](../INDEX.md) · [개발 계획](../development/DEVELOPMENT_PLAN.md) ·
[등록 수정 쌍 API](OWNER_POLICY_REPAIR_PAIR.md) ·
[변경 없는 S1 추천 API](OWNER_POLICY_RECOMMENDATION.md) ·
[이슈 #81](https://github.com/casing1/authzest/issues/81)

## 가용성과 경계 — 2026-10-29 KST

이 **미출시 소스 기능**은 #81에서 추적합니다.
`authzest.codex.owner_policy_repair_recommendation`의 순수 오프라인 선택 계약은
2026-10-24 KST에 [PR #102](https://github.com/casing1/authzest/pull/102)의 병합 `8409bc7`로
전달됐습니다. [PR #103](https://github.com/casing1/authzest/pull/103)의 소스 구현은
2026-10-25 KST에 `cc644a1`로 병합됐으며 별도 `codex-owner-repair` 명령에 전체 공유
미리보기·명시적인 1회 공유 결정·기존 Codex App Server 전송 연결을 추가합니다.
해당 커밋에서 새 별도 승인한 실제 시도 1회가 2026-10-28 KST에 성공했습니다. 아래의 제한된
수용 기록을 참고하세요. 전체 #81/#35의 완료나 정책 관찰·적용·복구를 입증하지는 않습니다.
공개 alpha.3에는 이 명령이 없습니다.

고정 수정 쌍 API는 2026-10-21 KST에 [PR #101](https://github.com/casing1/authzest/pull/101)의
병합 `cbe6b37`로 전달됐습니다. 이 확장은 정확히 그 등록 소스·기준·가정·검토한 예상값 8개·검토
기록 연결을 사용합니다. 검토 전문이나 URL을 내장하지 않고 hash로 고정합니다. 작성 이력을 변경하거나 기록된 예상값 결정을 인증된 승인·실행 동의·관찰
결과로 바꾸지 않습니다. 공개 alpha.3, 보고서 스키마 `1.2`, S1 스키마 `1.0` / 레지스트리
`empty-v1`, #80의 올바른 정책 worker는 그대로입니다. 부정 후보를 해당 worker 허용 목록에
추가하지 않습니다.

순수 계약에는 여전히 파일시스템/네트워크/제공자/프로세스 접근·대상 import/평가·파일 적용·복구가
없습니다. `policy.py`는 입력 경로가 아닌 논리적 표시 이름입니다. 임의 소스·저장소·callback·대체
수정 쌍·사례·예상값을 받지 않습니다. 프롬프트나 CLI 공유 미리보기를 렌더링해도 Codex에 아무것도
보내지 않습니다. 별도로 승인한 대화형 전송 경로만 Codex를 시작하며, 두 정책 후보를 실행하거나
선택한 diff를 적용하지 않습니다.

이 참조 문서는 추천 전용 기본 동작을 설명합니다. 별도 미출시
[`--file-workflow` 확장](../guides/OWNER_FILE_WORKFLOW.md)은 추가 복사본 결정과 개별 단계 결정이
있을 때만 현재 검증한 응답을 소유 파일 세션에 연결합니다. 공유 승인만으로는 실행·적용·복구를
허용하지 않습니다.

## 제한된 실제 수용 — 2026-10-28 KST

[수용 기록](https://github.com/casing1/authzest/issues/81#issuecomment-6458726176)은
`cc644a1`에서 기존 ChatGPT 로그인·Codex `0.153.0`·명시적 모델 `gpt-6-astra`를 사용해
새로 승인한 `before` 시도 1회를 기록합니다. 승인한 입력은 공개된 고정 합성 before/after
정책 쌍·기준·가정·검토한 예상값 8개·프롬프트·출력 스키마였습니다. 애플리케이션 turn 1개와
120초 timeout으로 제한했고 AuthZest 재시도·모델 대체는 없었으며 Codex 내부 재시도와 실제
사용량의 별도 상한은 보장하지 않았습니다. 전체 미리보기를 대조한 뒤 사용자 허가 아래 정확한
새 공유 문구를 입력했습니다.

- `30690.214375` ms에 `recommendation-ready` 흐름과 `registered-change` 결과를 받았습니다.
- 보고된 사용량은 입력 7,750·출력 697토큰이며 경고 1개·재시도 알림 0개였습니다. 이는 보고된
  전송 관찰이며 서명된 제공자 증표나 보고되지 않은 내부 재시도가 없었다는 보장은 아닙니다.
- 모델은 기존 등록 수정 템플릿을 선택했으며 임의 대체 코드를 생성하지 않았습니다. Host가 diff를
  도출했고 결과·근거 참조·합성한 diff의 오프라인 재검증을 통과했습니다.
- 두 정책 모두 실행하지 않았습니다. 적용/복구는 `not-run`, 전후 관찰은 null, 비교는
  `not-evaluated`, 인가는 `unknown`을 유지했고 원본 checkout도 그대로입니다.

이 1회 공유 승인은 소비됐습니다. 제한된 연동 수용 1회이지 독립 벤치마크·일반적인 모델 품질 결과나
수정이 관찰된 동작을 바꾼다는 증명은 아닙니다. 이후 관리자는
[전용 검사 설계와 오프라인 구현을 승인했습니다](https://github.com/casing1/authzest/pull/110#issuecomment-6459020000).
PR #110은 `510377c`에서 최초 오프라인/프로세스 mock 검증을 수행한 별도
[등록 후보 검사 Python API](OWNER_POLICY_REPAIR_CHECK.md)를 추가합니다. 이후 같은 커밋에서
별도 승인한 before 전용 실행을 예상한 두 불일치, 종료 `0`, 정리 확인으로 완료했습니다.
[별도 수용 기록](https://github.com/casing1/authzest/pull/110#issuecomment-6460245210)을 참고하세요.
해당 before 승인은 소비됐습니다. 이후 [별도 승인한 after 전용 실행](https://github.com/casing1/authzest/pull/110#issuecomment-6460474112)은
문서 전용 `7f9c5ce`에서 같은 런타임 소스로 사례 8개 일치·종료 `0`·정리 확인을 기록했습니다.
두 런타임 승인은 모두 소비됐습니다. 이 별도 검사들은 위 추천 시도의 원래 null 관찰 기록을
바꾸지 않습니다. 내장 after는 대조군이지
적용 파일 검증이 아닙니다. #80 worker는 변경하지 않으며 부정 후보를
계속 거절합니다. #81/#35/#82는 열려 있습니다.

## CLI: 먼저 미리보고 선택적으로 공유

이 작업을 포함한 소스 설치를 사용하세요. 기존 Codex ChatGPT 계정에서 사용할 수 있는 정확한
모델 식별자를 지정하며 모델을 자동 선택하거나 대체하지 않습니다. 실제 응답을 요청하기 전에
아래 `YOUR_EXACT_MODEL_ID`를 바꾸세요. 다음 미리보기 명령은 모두 오프라인입니다.

```bash
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --preview-only
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --candidate after --timeout-seconds 120 --preview-only --json
```

미리보기에는 전체 고정 요청, 두 소스 snapshot, 정책 기준, 신뢰 가정, 검토한 사례 예상값 8개,
정확히 렌더링한 프롬프트와 요청 출력 스키마가 포함됩니다. 선택한 모델, host 설정/제한, 새 공유
challenge도 표시합니다. 요약이나 hash만이 아닌 실제 내용을 검토해야 합니다. 저장소 경로를 받거나
소스로 읽지 않습니다. `--preview-only`는 인증을 확인하거나 제공자 프로세스를 시작하지 않습니다.
이는 AuthZest가 제어하는 전체 입력이며 Codex가 별도 harness 문맥을 추가하고 계정의 데이터
처리 규칙이 적용됩니다. 제공자 측 전체 문맥을 바이트 단위로 재현하는 미리보기는 아닙니다.

응답 1회를 요청하려면 `--preview-only` 없이 실행하세요.

```bash
authzest codex-owner-repair --model YOUR_EXACT_MODEL_ID --candidate before --timeout-seconds 120
```

새 전체 미리보기를 검토한 뒤 해당 실행에 표시한 ID로 정확히 `share <sharing_id>`를 입력하세요.
미리보기 전용 ID나 복사한 과거 결정은 이후 실행의 권한이 아닙니다. 공유 전에 거절하거나 취소하면
요청을 보내지 않습니다. 비대화형 승인 flag는 없습니다. 후보 기본값은 `before`이며 `after`는
올바른 정책의 변경 없음/불명 경로를 유지합니다.

실제 경로는 POSIX가 필요하며 버전을 고정한 기존 Codex `0.153.0` App Server 전송과 기존
ChatGPT 로그인을 사용합니다. 미리보기 전용 경로는 POSIX나 해당 Codex 설치가 필요하지 않습니다.
API 키를 만들지 않으며 AuthZest는 애플리케이션 수준으로 한 번 시도하고 재시도나
모델 대체를 하지 않습니다. Codex/제공자 내부 통신 재시도와 실제 사용량/과금은 이 횟수 제한이나
timeout으로 별도 상한을 보장하지 못합니다. 공유 결정은 이 요청만 허용하며 정책 실행·패치 적용·
검증·복구를 허용하지 않습니다.

기본 출력은 사람이 읽기 쉬운 형식입니다. `--json`은 최종 결과를 stdout에, 대화형 미리보기·질문·
진행 상황을 stderr에 출력하고, `--preview-only --json`은 전체 오프라인 미리보기를 stdout에
출력합니다. 설명 문자열은 지시가 아닌 신뢰하지 않는 표시 데이터로 취급하세요. adapter는 정확한
요청에 연결해 응답을 검증한 뒤 host가 도출한 diff를 합성합니다. `registered-change`는
`before`에만 유효하며 `no-change`와 `unknown`도 유효한 결과입니다. 검증 실패나 전송 실패는
정책이 안전하거나 수정이 성공했다는 근거가 아닙니다.

순수 결과 미리보기는 해당 순수 합성 단계를 설명하므로 호출자 제공 데이터 출처와 제공자 호출
`0`을 유지합니다. 별도 adapter metadata가 host의 전송 시도를 보고하지만 서명된 제공자 증명은
아니며 모델 설명이나 검토한 예상값을 관찰된 정책 동작으로 바꾸지 않습니다. 기존
`codex-owner-review`, S1 계약, #80 worker는 그대로입니다.

CLI 미리보기/결과의 `request_id`는 선택한 모델과 출력 스키마를 포함한 전송 요청을,
`recommendation_request_id`는 변경하지 않은 모델 독립 선택 요청을 식별합니다. 성공한 흐름의
`recommendation`에는 전송 envelope가, `recommendation_preview`에는 순수 합성 결과가
들어갑니다. `application_turn_attempts`는 host adapter 시도 수이며 성공한 제공자 turn이나
과금 호출 수가 아닙니다.

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

Canonical/원시 UTF-8 계약 요청/결과, 전체 순수 합성 미리보기, 렌더링한 프롬프트는
262,144바이트, JSON 깊이는 최대 32, 방문 node는 최대 8,192개입니다. 순수 합성 미리보기의
metadata와 중첩된 등록 수정 쌍 미리보기도 제한에 포함합니다. 바깥 CLI 공유/흐름 출력은 payload를
반복하므로 전체가 262,144바이트로 제한되지는 않습니다.
일반 설명은 4,096자, ID는 128자까지입니다. 공통 decoder는 소스를 묵시적으로
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
print(
    json.dumps(
        {
            "prepared_prompt": owner_policy_repair_recommendation_prompt(request),
            "preview": preview.to_dict(),
        },
        ensure_ascii=True,
        indent=2,
    )
)
```

## 검증과 남은 gate

오프라인 검증은 두 후보와 모든 상태, 정확한 요청/프롬프트/근거/사례 연결, 과거·위조·분리된
데이터, 닫힌 필드와 전체 산출물 크기 경계, 부작용·정책 import/평가 방지를 다뤄야 합니다.
이는 요구사항이지 여기서 주장하는 결과가 아닙니다.

공유/adapter 검사는 scripted 전송 응답, 거절/취소, 정확한 공유 연결과 실패 사례도 다룹니다.
오프라인 테스트는 실제 모델 수용 근거가 아닙니다. 위의 별도 2026-10-28 수용은 해당 1회 공유
승인을 소비했으며 추가 제공자 검사에는 새 범위 제한 결정이 필요합니다.
[전용 고정 검사 API](OWNER_POLICY_REPAIR_CHECK.md)는 검토한 recipe를 PR #110에서 구현하며
`510377c`의 최초 검증은 오프라인/정적/mock이었습니다. 이후 별도 승인한 before 실행은 예상한
두 불일치를 기록했고 해당 1회 승인을 소비했습니다. 이후 별도 after 실행은 문서 전용 `7f9c5ce`에서
before 재실행이나 런타임 변경 없이 사례 8개가 일치했고 자체 승인을 소비했습니다. 보존 기록의
오프라인 비교는 새 제품 비교 API나 인증된 실행 증명이 아닙니다. #80은 부정 소스를 계속 거절합니다.
이후 PR #110은 별도 승인한 최종 head 리뷰와 전달을 2026-10-28 `ea081e0`에서 완료했습니다.
[소스 전달 기록](OWNER_POLICY_REPAIR_CHECK.md#소스-전달-완료--2026-10-28-kst)을 확인하세요.
이후 별도 검토한 파일 식별값 연결 API를 PR #118에서 전달했습니다. 2026-10-29 `fb90c46`의
[파일 흐름 수용](OWNER_POLICY_FILE_REPAIR.md#file-workflow-acceptance--2026-10-29-kst)은
과거 실제 추천을 재검증하고 before 검사·정확한 diff·적용·after 검사·복구 각각의 승인을
소비했습니다. 새 제공자 호출 없이 before 6/8, 적용 after 8/8 일치를 관찰하고 소유 복사본을
복구했습니다. 이는 소스 API 수용이지 새 모델 수용이나 설치형 CLI 통합이 아니며, 내장 after
대조군은 여전히 적용 파일을 검증할 수 없습니다. 별도 [#82 선택형 CLI 구현](../guides/OWNER_FILE_WORKFLOW.md)은
가짜 adapter/scripted worker의 오프라인 검증과 이후 별도 승인한 `c868152` 설치형 정상 경로 관찰을
구분합니다. 현재 추천·캡처 before 6/8·정확한 diff/적용·실제 적용 after 8/8·복구를 확인했습니다.
전체 출력/비공개 증거 검증과 한계는 [설치 관찰 기록](../guides/OWNER_FILE_ACCEPTANCE.md)에 있으며
최종 #82 수용 검토는 미완료입니다.
이 데이터 객체나 유효한 제공자 결과는 실행·패치·병합·태그·릴리즈를 허용하지 않습니다.
더 넓은 #81/#82와 프리릴리즈 gate는 열려 있습니다.
