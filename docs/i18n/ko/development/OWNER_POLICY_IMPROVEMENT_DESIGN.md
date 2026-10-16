<p align="center">
  <a href="../../../development/OWNER_POLICY_IMPROVEMENT_DESIGN.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소유 정책 개선 설계

[문서 목차](../INDEX.md) · [개발 계획](DEVELOPMENT_PLAN.md) ·
[고정 정책 검사](../reference/OWNER_POLICY_CHECK.md) · [이슈 #81](https://github.com/casing1/authzest/issues/81)

## 상태와 검토할 결정

**제안 상태, 미구현 — 2026-10-15 KST.** #81의 첫 오프라인 추천 계약과 읽기 전용 미리보기만
명세합니다. 새 API·CLI 명령·모델 호출이나 승인한 패치 흐름이 아닙니다. 구현 전에 관리자 설계
검토가 필요합니다. 문서 검사 통과나 이 설계의 병합은 해당 승인을 기록하거나 #81을 완료하지 않습니다.

기준은 [PR #97](https://github.com/casing1/authzest/pull/97)로 #80을 병합한 main
`38587c30e644aa459cdd5242faf279f44ffa2240`입니다. 별도로 승인한 `e037986`의 recipe `1.1`
소스 실행에서 검토한 예상값 10개가 모두 일치했고 원래 recipe `1.0` 관찰은 별도로 보존합니다.
두 1회 승인은 소비됐습니다. 과거 순수 정책 관찰이지 HTTP/인증 수용·새 모델 답변이나 다른
검사를 실행할 권한이 아닙니다.

다음의 제한된 선택을 검토합니다. 등록된 정책 snapshot 하나와 정책 기준만 입력하고 결과는
`no-change`·`unknown`으로 제한하며 변경 쌍 registry는 비웁니다. 첫 요청 스키마는 사례·정답·
관찰을 제외하고 과거 결과를 현재 실행 근거로 가져오지 않습니다. 나중에 포함하려면 별도로
검토한 버전과 정확한 산출물 연결이 필요합니다.

## 기존 계약 유지

기존 소유 정책 검토는 소스 snapshot 두 개를 연결해 답변·사례를 반환합니다. 해당 공유 결정은
이 새 입력이나 패치를 포함하지 않습니다. 일반 제안 계약은 변경을 필수로 요구하고 호출자가
작성한 교체를 최대 8개 허용합니다. 이번 단계 때문에 어느 계약도 완화하지 않아야 합니다.
#80 worker는 등록된 올바른 정책만 계속 받으며 소스·recipe·실행 허용 목록은 유지합니다.
유효한 추천은 실행 권한이 아닙니다.

## 제안하는 요청

순수 builder는 등록된 메모리 상수만 사용하도록 합니다. 경로·임의 소스·저장소·모델 선택·
callback·사례 묶음·정답 기록·관찰 기록은 받지 않습니다. 논리 이름 `policy.py`는 표시할
데이터를 식별하며 열 파일이나 패치 목적지가 아닙니다.

제안 스키마 버전은 `1.0`이며 리포트 스키마 `1.2`·기존 소유 정책 검토 스키마·패키지 버전
`0.1.0a3`와 독립적입니다. 다음은 요청 payload의 전체 필드입니다.

| 필드             | host가 소유하는 값 또는 규칙                                                                         |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| `schema_version` | 정확히 `1.0`                                                                                         |
| `kind`           | 정확히 `owner-policy-recommendation-request`                                                         |
| `scenario_id`    | 정확히 `owned-report-read-policy-v1`                                                                 |
| `source`         | `path`·`text`·`sha256`·`evidence_id`만 포함; 등록된 `policy.py` 바이트만 허용                        |
| `criteria`       | `text`·`sha256`·`evidence_id`만 포함; 아래 제안하는 정책 전용 snapshot                               |
| `assumptions`    | `id`·`text`만 포함하는 고정 순서 객체: 신뢰하는 principal, 신뢰하는 소유권 조회, 합성 순수 정책 범위 |
| `registry`       | `version`·`pairs`만 포함; 버전 `empty-v1`과 빈 배열                                                  |

소스 바이트는 주변 파일이 아닌 [유지하는 소스 template](../../../../src/authzest/codex/owner_policy_review.py)의
기존 `OWNER_POLICY_SOURCE` 상수입니다. 텍스트 해시는 줄 끝을 포함한 정확한 UTF-8 바이트를
사용합니다. 소스 근거는 `owner-recommendation-source-` prefix와 `path`·`text`·`sha256`
객체의 canonical 해시를 사용합니다. 기준 근거는 `owner-recommendation-criteria-` prefix와
`text`·`sha256` 객체의 canonical 해시를 사용하며 어느 쪽도 자신의 `evidence_id`를 포함하지
않습니다. 요청 ID는
`owner-recommendation-request-`에 전체 payload의 공통 canonical SHA-256을 붙입니다.
host가 도출하는 속성이지 자기 참조하는 payload 필드가 아닙니다. 관련 바이트·버전이 바뀌면
ID도 바뀌고 과거 결과는 유효하지 않습니다. 해시는 내용을 식별할 뿐 신원이나 승인을 증명하지 않습니다.

제안하는 새 기준 snapshot은 이전에 승인한 정책 의미를 유지하지만 과거 소유 정책 검토
프롬프트의 정답 검토 문장은 가져오지 않습니다. 다음의 정확한 새 문구도 이번 검토 범위입니다.

```text
Allow a report read only for an already trusted principal whose authenticated value is exactly true, whose scopes contain the literal reports:read value, and whose subject exactly matches a trusted report owner. Deny missing or malformed principal/report context, blank identifiers or malformed scopes. Do not normalize identifiers. There is no administrator, wildcard or ownership exception. This pure predicate does not authenticate inputs or prove HTTP enforcement.
```

이 기준 값은 위의 한 줄이며 끝에 LF가 없습니다. 코드 fence를 닫는 줄바꿈은 문자열에 포함되지
않습니다. 반면 소스 상수는 원래의 모든 줄 끝을 유지합니다. 요청의 정확한 순서가 있는 가정은
다음과 같습니다.

```json
[
  {
    "id": "trusted-principal",
    "text": "The caller supplies an already trusted principal; constructing a dataclass does not authenticate identity, scopes or authentication claims."
  },
  {
    "id": "trusted-ownership",
    "text": "Report ownership and report identity come from a trusted lookup, not request-supplied claims."
  },
  {
    "id": "synthetic-pure-policy",
    "text": "Only the maintained synthetic pure predicate is in scope; HTTP, authentication-provider, database and endpoint enforcement are not evaluated."
  }
]
```

이 snapshot을 도입하려고 기존 `OWNER_POLICY_TEXT`를 수정하거나 모델·정답 이력을 다시
작성하지 마세요. principal/report 데이터를 구성한다고 요청이 제공한 신원·소유권을 신뢰할 수
있는 것은 아닙니다.

## 제안하는 원시 결과

아래 필드만 받습니다. 호출자가 제공한 상태·소스 해시·타입 wrapper로 현재 등록 요청에 대한
재검증을 우회할 수 없습니다. 이 데이터는 호출자가 작성하거나 고정 응답으로 만들 수 있으며
형식이 유효하다고 Codex가 생성했거나 설명이 옳다는 뜻은 아닙니다.

| 필드               | 검증                                                                     |
| ------------------ | ------------------------------------------------------------------------ |
| `schema_version`   | 정확히 `1.0`                                                             |
| `request_id`       | 현재 host가 도출한 정확한 요청 ID                                        |
| `status`           | 정확히 `no-change` 또는 `unknown`                                        |
| `rationale`        | 비어 있지 않은 제한된 텍스트                                             |
| `evidence_ids`     | 소스·기준 ID 모두 포함; 알 수 없거나 중복한 ID는 없음                    |
| `assumptions`      | 각 항목이 비어 있지 않은 제한된 텍스트 목록; 최소 1개 항목               |
| `uncertainties`    | 각 항목이 비어 있지 않은 제한된 텍스트 목록; `unknown`이면 최소 1개 항목 |
| `expected_effects` | 각 항목이 비어 있지 않은 제한된 텍스트 목록; 최소 1개 항목               |
| `limitations`      | 각 항목이 비어 있지 않은 제한된 텍스트 목록; 어느 상태든 최소 1개 항목   |
| `change_pair_id`   | 정확히 JSON null; null이 아닌 모든 값은 거절                             |

`no-change`는 이 입력 범위에서 소스 변경을 뒷받침할 근거가 없다는 뜻이지 보안 통과가 아닙니다.
`unknown`은 추천에 필요한 근거의 부족을 식별하며 거절값이나 관찰 실패를 만들어내지 않습니다.
지시·코드처럼 보이는 텍스트를 포함해 자유 형식 설명은 데이터로 유지합니다. 구조 검증으로
의미상 근거·신뢰하는 인증이나 endpoint 강제를 입증할 수 없습니다.

비어 있어도 추가 필드는 거절합니다. 교체 소스·`after_text`·`changes`·`diffs`·패치·명령·
실행 가능한 테스트·사례·정답·관찰·제공자/모델 신원 주장·승인 선택·실행/적용 상태는 이 원시
스키마 밖입니다.

## host 미리보기와 초기 registry

제안하는 순수 미리보기는 두 산출물을 재검증하고 분리된 요청/결과 snapshot·각 ID·정확한
내용 해시·registry 버전을 반환합니다. 추천 ID는 `owner-recommendation-` prefix와 요청 ID를
포함한 검증된 원시 결과의 canonical 해시를 사용합니다. 전체 미리보기 객체는 아래 필드만
가집니다. 출력 전용이며 제출한 미리보기를 승인 입력으로 사용하지 않습니다. host가 모든 필드를
다시 만들며 원시 결과가 덮어쓰는 것은 허용하지 않습니다.

| 미리보기 필드          | 이번 단계의 고정 값                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------- |
| `schema_version`       | 정확히 `1.0`                                                                          |
| `kind`                 | 정확히 `owner-policy-recommendation-preview`                                          |
| `request_id`           | 현재 host가 도출한 요청 ID                                                            |
| `recommendation_id`    | 현재 host가 도출한 추천 ID                                                            |
| `request`              | 분리된 완전한 검증 요청 payload                                                       |
| `recommendation`       | 분리된 완전한 검증 원시 결과                                                          |
| `source_sha256`        | 현재의 정확한 `source.sha256`                                                         |
| `criteria_sha256`      | 현재의 정확한 `criteria.sha256`                                                       |
| `registry_version`     | 정확히 `empty-v1`                                                                     |
| `changes` / `diffs`    | 빈 배열                                                                               |
| `provider_calls`       | 이 연산에서 `0`                                                                       |
| `execution_status`     | `not-run`                                                                             |
| `patch_application`    | `not-run`                                                                             |
| `restoration_status`   | `not-run`                                                                             |
| `authorization_status` | `unknown`                                                                             |
| `provenance`           | `kind` = `caller-supplied-data`와 `authenticated` = JSON false만 포함; 다른 키는 없음 |

registry를 채우는 생성자 옵션은 없습니다. 나중에 쌍을 등록하려면 명시적으로 소유한 합성
시나리오·정확한 변경 전후 바이트·해시·버전을 관리자가 검토해야 합니다. 그 뒤에만 별도로 검토한
확장이 쌍 ID를 받고 host에서 단일 파일 diff를 도출할 수 있습니다. 여기서는 부정 시나리오
변형이나 교체 소스를 제안하지 않으며 수정 시연만을 위해 현재의 올바른 정책을 취약하다고
표시해서는 안 됩니다.

미리보기는 검토 가능한 데이터이지 renderer나 승인 서비스가 아닙니다. 이후 표시 계층은
예를 들어 ASCII 이스케이프한 JSON으로 모든 비신뢰 텍스트를 이스케이프해야 하며 이를 실행하거나
Markdown/터미널 제어 문자를 권한으로 취급해서는 안 됩니다. ID·직렬화 snapshot·복사한
미리보기는 공유·적용·검증·복구 권한을 부여하지 않습니다.

## 검증 한도와 오프라인 수용

기존 공통 JSON 규칙은 들어오는 결과뿐 아니라 요청·원시 결과·불변 snapshot·완성된 host
미리보기 모두에 적용합니다. 이 연산에는 파일시스템/제공자/프로세스 접근이나 정책 평가가 없습니다.

| 경계                          | 제안 한도                          |
| ----------------------------- | ---------------------------------- |
| 완전한 canonical UTF-8 산출물 | 262,144바이트                      |
| JSON 깊이 / 방문 노드         | 32 / 8,192                         |
| 등록 소스 텍스트              | 32,768자                           |
| 일반 텍스트 항목 하나         | 4,096자                            |
| ID 하나                       | 128자                              |
| 텍스트 목록 하나              | 최대 32개 항목; 최솟값은 위와 같음 |
| 근거 ID                       | 서로 다른 등록 ID 정확히 2개       |

정확한 객체 키·scalar 타입을 요구하며 boolean·숫자·문자열·null을 변환하지 않습니다. 중복 JSON
키·비유한 숫자·유효하지 않은 Unicode·공통 텍스트 helper가 거절하는 제어 문자는 거절합니다.
일반 텍스트에 TAB/LF/CR은 허용하며 helper가 모든 bidi/zero-width 문자를 막지는 않습니다.
안전한 표시는 여전히 필요합니다.

구현 PR은 다음을 다루어야 합니다.

- 두 상태의 유효 결과·분리된 snapshot·결정적 식별값·빈 changes/diffs.
- 누락/추가/중복 키·잘못된 타입/상태/버전·객체가 아닌 JSON.
- 소스/기준/줄 끝/해시/가정/registry 변경·과거 또는 직접 위조한 wrapper.
- 누락/알 수 없음/중복 근거·빈 필수 목록·null이 아닌 모든 변경 쌍 ID.
- 비어 있는 값까지 포함한 금지 소스/diff/명령/사례/관찰/승인 필드.
- 최종 host 메타데이터 증가까지 포함한 문자·UTF-8·깊이·노드·collection 경계.
- 파일시스템/네트워크/제공자/프로세스 효과·대상 import/평가에서 실패하는 guard.

이미 추가하거나 통과한 테스트가 아니라 제안하는 테스트입니다. 고정 응답은 고정 응답이라는
사실을 명시해야 합니다. 오류 진단은 소스·원시 payload를 되풀이하지 않고 기존의 고정 코드만
사용해야 합니다.

## 검토와 전달 gate

1. 구현 전에 관리자가 이 정확한 첫 단계 입력·출력·거절 설계를 검토합니다.
2. guard가 있는 오프라인 테스트·대응하는 영한 문서와 함께 순수 계약/미리보기만 구현합니다.
3. casing1·기존 라벨·마일스톤 04의 범위가 명확한 PR을 사용하며 필수 CI·리뷰를 일반 gate로 유지합니다.
4. 스키마나 #80 worker를 확장하기 전에 사례/정답/관찰 연결·필요한 경우 부정 test-only 시나리오·
   등록 수정 쌍을 별도로 검토합니다.
5. 이후 실제 제공자 요청에는 자체 최소 공유 미리보기와 범위 제한 승인이 필요합니다. 소스 공유·
   정답 검토·변경 전 검사·정확한 diff 적용·변경 후 검사·복구는 각각 현재 상태에 대한 별도 결정입니다.
   원래 checkout과 이후 사용자 변경을 보존합니다.

이 설계는 유료/수동 재리뷰·모델 호출·코드 실행·패치·릴리스·태그 권한을 부여하지 않습니다.
새 CLI·제공자 adapter·의존성·workflow나 기존 scan 동작 변경은 추가하지 않습니다.
전체 #81과 #82의 설치형 통합 수용은 계속 열려 있습니다.
