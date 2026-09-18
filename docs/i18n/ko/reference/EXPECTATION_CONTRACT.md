<p align="center">
  <a href="../../../reference/EXPECTATION_CONTRACT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 근거 연결 예상 결과 계약

[문서 목차](../INDEX.md) · [제안·결정 계약](PROPOSAL_CONTRACT.md)

## 구현 범위

[#61](https://github.com/casing1/authzest/issues/61)은 #35의 하위 단계로 호출자가 작성하는 순수 예상 결과
manifest를 추가합니다. alpha.3 이후 소스 checkout에 추가한 미출시 기능이며 자체 스키마는 `1.0`입니다.
패키지 버전 `0.1.0a3`, 리포트 스키마 `1.2`와 기존 제안·결정 스키마는 바뀌지 않습니다.
구현은 [codex/expectations.py](../../../../src/authzest/codex/expectations.py)에 있습니다.

manifest는 이후 검토를 위해 정확한 제안을 기준 소스·등록 근거, 인용한 정책, 의도한 결과에 연결합니다.
테스트를 생성하거나 제공자를 호출하거나 파일을 읽고 쓰지 않으며 소스·프로세스·네트워크 작업도
실행하지 않습니다. 별도 [#63 CLI 미리보기](../guides/PROPOSAL_PREVIEW.md)는 검증된 오프라인
bundle에서 이를 표시합니다. 이후 [#69 소스 전용 검사](../guides/PROPOSAL_CHECK.md)는 해당
bundle의 지원 범위 내 소스 snapshot을 선언 목표와 비교합니다. adapter·패치 적용·실행 서비스나
승인 결정은 이 manifest를 사용하거나 여기에 연결되지 않습니다. 기존의 고정된
설정·health fixture 흐름은 그대로이며 #35와 더 넓은 방어적 회귀 테스트 초안 생성은 미완료입니다.

## 연결한 데이터와 검증

`prepare_expectation_manifest`는 요청, 해당 요청의 검증된 검토, 정확한 제안과 호출자가 작성한
예상 결과 목록을 받습니다. `validate_expectation_manifest`는 해당 산출물을 다시 검증하고 정확한
스키마 필드만 허용합니다. 명령이나 실행 가능한 테스트 언어가 아닙니다.

- manifest는 `request_id`, `review_id`, `proposal_id`, `source_identity`에 연결됩니다.
  `manifest_id`는 `expectation-` 뒤에 정규화한 payload의 SHA-256을 붙인 값입니다. 예상값·정책 참조·한계를
  포함한 모든 실질적인 내용이 이 식별값에 반영됩니다.
- 각 예상 결과에는 `id`, `source_evidence_id`, `route_evidence_id`, `policy_evidence_ids`,
  `observation`, `expected`, 비어 있지 않은 `limitations`를 제공합니다. 소스와 라우트는 같은 요청에
  속하는 올바른 종류의 근거여야 하며 같은 파일을 가리켜야 하고, 제안은 그 파일을 수정해야 합니다.
  각 정책 참조는 해당 요청의 정책 근거를 가리켜야 합니다. 인용만으로 정책이 예상 결과를 의미상
  뒷받침하거나 정책 소유자가 승인했다는 사실을 입증하지는 않습니다.
- 준비 함수는 해당 산출물에서 `path`, `baseline_registration_id`, `before_sha256`, `after_sha256`을
  도출합니다. 검증은 제공된 연결값이 일치하지 않으면 거부합니다. 정확한 UTF-8 소스·변경 내용 해시는
  줄바꿈을 보존합니다. 등록 ID는 소스 위치를 포함한 기준 등록을 식별하며 패치 뒤에도 같은 값이
  유지된다고 보장하지 않습니다.
- manifest는 `[a-z][a-z0-9-]{0,63}`에 맞는 고유 ID를 가진 예상 결과 1–32개를 받습니다.
  `(baseline_registration_id, observation)` 쌍의 반복은 거부합니다. 각 예상 결과에는 고유 정책 참조
  1–16개와 비어 있지 않은 한계 설명 1–16개가 필요합니다. AI 계약의 제한된 JSON 파싱 규칙도 적용합니다.
- 누락·다른 요청·잘못된 종류의 근거, 오래된 연결값, 중복 참조, 미지원 관찰 종류와 예상 밖 필드는
  `ContractError`를 발생시킵니다. shell·환경·설치 hook·관찰 결과·승인 필드를 추가 manifest 필드로 받지
  않습니다. 설명문은 계속 비신뢰 표시 데이터입니다.

불변 wrapper는 정규화한 JSON을 보관하며 `to_dict()`와 미리보기는 분리된 데이터를 반환합니다.
소비자는 `ValidatedExpectationManifest` wrapper도 다시 검증해야 합니다. 이는 내용 연결이지 서명된
권한 기록이나 fixture 소유권·의미상 정확성·현재 디스크/Git 상태의 최신성을 보장하는 것이 아닙니다.

## 예상 결과의 의미

| `observation`             | 정확한 `expected` 형태                                                         | 의도한 의미이며 관찰된 결과는 아님                                                             |
| ------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `policy-intent`           | `{"intent": "public"}`; `restricted`, `unspecified`도 허용                     | 인용 정책에 대한 호출자의 해석이며 자동 정책 대조나 강제 적용 주장이 아님                      |
| `dependency-declarations` | `{"count": 1}`; boolean이 아닌 정수 0–256                                      | 선택한 등록의 유효 의존성 선언 수 목표이며 일반 DI는 접근통제 근거가 아님                      |
| `scope-declarations`      | `{"scopes": ["items:read"]}`; 고유하며 비어 있지 않은 최대 256자 문자열 0–32개 | 해당 등록의 유효 의존성에 걸친 고유 scope 선언 목표이며 선언은 scope 강제 적용을 입증하지 않음 |

이 값들은 호출자가 작성한 목표이며 이 순수 계약 모듈은 소스를 파싱하거나 비교하지 않습니다.
별도 [#69 검사기](../guides/PROPOSAL_CHECK.md)가 지원하는 기준·제안 snapshot을 재파싱하고
선언 비교를 보고하지만 `policy-intent`는 항상 `not-evaluated`입니다.
기준 근거는 부분적일 수 있고 manifest는 제안 변경 중 일부만 다룰 수 있습니다.
빈 scopes 목록이나 선언 수 0은 endpoint가 공개·안전·취약하다는 finding이 아닙니다. 공개 의도는
실제 공개 동작을 입증하지 않으며 제한 의도도 인가를 입증하지 않습니다.

`expectation_preview`는 항상 `status: draft`, `verification_status: not-run`, `observed: null`,
`authorization_verdict: unknown`을 반환합니다. 정책 의도에는 `caller-policy-interpretation`,
선언 예상 결과에는 `source-declaration-target`을 표시하고 명시적인 한계를 유지합니다. 검증 성공은
구조적 일관성만 뜻하며 검증 실행 통과나 보안 문제 수정이 아닙니다.

기존 제안 결정은 별도 버전의 이 manifest에 연결되지 않습니다. 예상 결과 변경은 새 manifest 식별값을
만들지만 현재 제안 전용 결정을 무효화하지는 않습니다. 향후 실행 연동에서는 검토한 manifest를
자체 정확한 계획·별도 승인에 연결하고 고정 검사기·결과 계약을 정의하며 실제 상태를 다시 확인해야
합니다. 이 산출물을 제한 없는 실행기에 연결하지 마세요.

## Python API와 오프라인 검사

아래 예시는 `request`, `review`, `proposal`이 이미 존재하고 호출자가 수정 파일과 해당 기준 등록에
대해 같은 요청의 근거 ID 3개를 검토했다고 가정합니다. `public`은 설명을 위해 호출자가 작성한 목표이며
API가 추론한 분류가 아닙니다.

```python
from authzest.codex.expectations import (
    expectation_preview,
    prepare_expectation_manifest,
)

manifest = prepare_expectation_manifest(
    request,
    review,
    proposal,
    expectations=[
        {
            "id": "policy-intent-1",
            "source_evidence_id": source_evidence_id,
            "route_evidence_id": route_evidence_id,
            "policy_evidence_ids": [policy_evidence_id],
            "observation": "policy-intent",
            "expected": {"intent": "public"},
            "limitations": ["Caller-authored intent; enforcement is not established."],
        }
    ],
)
preview = expectation_preview(manifest, request, review, proposal)
```

editable 개발 환경 설치 후 저장소 루트에서 실행합니다.

```bash
python -m pytest tests/test_expectation_contract.py
```

테스트는 기존 공개 의도·일반 DI·scope 선언 개발 사례에 호출자가 작성한 mock 예상 결과를 사용합니다.
고정한 평가셋 바이트와 별도 평가 사례는 바꾸지 않습니다. 구조·참조 거부, 식별값 변경, 분리된 직렬화와
I/O 금지를 검사하며 모델 품질·실제 대상 관찰·인가 정확성은 검증하지 않습니다. 이 오프라인 단계가
실제 Codex 검증이나 릴리스를 뜻하지는 않습니다.
