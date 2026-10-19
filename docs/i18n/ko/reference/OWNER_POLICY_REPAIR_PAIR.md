<p align="center">
  <a href="../../../reference/OWNER_POLICY_REPAIR_PAIR.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 등록 소유 정책 수정 쌍 API

[문서 목차](../INDEX.md) · [개발 계획](../development/DEVELOPMENT_PLAN.md) ·
[과거 수정 쌍 설계](../development/OWNER_POLICY_REPAIR_PAIR_DESIGN.md) ·
[S1 추천 API](OWNER_POLICY_RECOMMENDATION.md) ·
[이슈 #81](https://github.com/casing1/authzest/issues/81)

## 사용 가능 범위와 경계 — 2026-10-19 KST

이 브랜치는 `authzest.codex.owner_policy_repair_pair`에 순수 Python 데이터 API를 구현합니다.
등록된 합성 소스 쌍 하나, 정확한 케이스/라벨 및 기록된 검토 binding, host가 도출한 단일 파일
diff 미리보기를 제공합니다. 이 소스 구현은 아직 병합하거나 출시하지 않았습니다.
#81/#35를 완료하거나 CLI·제공자 요청·정책 실행·파일 적용을 추가하지 않습니다.
공개 alpha.3는 그대로입니다.

변경하지 않은 [수정 쌍 설계](../development/OWNER_POLICY_REPAIR_PAIR_DESIGN.md)는
2026-10-19 KST에 [PR #100](https://github.com/casing1/authzest/pull/100)으로
`c12f4b137b30f96202b3a2555b3b5a151edf6e56`에 전달됐습니다. 이는 구현 기준이며 최신
main이라는 뜻은 아닙니다. 관리자는 정확한 시나리오/소스 쌍과 어시스턴트가 작성한 예상값 8개
모두, 이어서 이 제한된 순수 레지스트리/미리보기 단계를 별도로 승인했습니다.
[기록한 결정](https://github.com/casing1/authzest/pull/100#issuecomment-6258235318)을 참고하세요.
원래 작성 이력은 어시스턴트 작성으로 유지됩니다. 이 기록은 인증된 승인 권한, 실행 동의,
관찰, 새로운 모델 응답 또는 유지·관리되는 평가셋이 아닙니다.

API는 호출자가 선택한 경로·소스·쌍·레지스트리·케이스·라벨·검토 기록·모델·callback을 받지
않습니다. 어느 정책 후보도 import/평가하지 않고 대상 파일 읽기/쓰기, 파일시스템/네트워크/제공자/
프로세스 접근, 패치 적용 또는 복구를 하지 않습니다. `policy.py`는 열어 볼 경로가 아닌 논리적
표시 라벨입니다. S1 스키마 `1.0`/레지스트리 `empty-v1`, null이 아닌 변경 쌍 ID의 거부,
#80의 올바른 정책 worker/허용 목록 및 모든 과거 #77 모델/검토/관찰 기록은 그대로입니다.
올바른 정책에 대한 `no-change`/`unknown`은 계속 유효합니다.

## Python 진입점

| 진입점                                           | 결과                                                                     |
| ------------------------------------------------ | ------------------------------------------------------------------------ |
| `build_owner_policy_repair_pair()`               | 등록된 `OwnerPolicyRepairPair` 하나 생성; 설정 인자 없음                 |
| `validate_owner_policy_repair_pair(raw)`         | 현재 등록된 정확한 전체 manifest를 재구성하고 검증                       |
| `prepare_owner_policy_repair_pair_preview(pair)` | 쌍을 재검증하고 diff 하나를 포함하는 `OwnerPolicyRepairPairPreview` 반환 |

쌍은 파생 속성 `pair_id`를 제공하며 두 wrapper의 `to_dict()`는 분리된 데이터를 반환합니다.
validator의 `raw` 인자는 직렬화한 JSON 텍스트이며 dictionary, 파일 경로 또는 실행 가능한 입력이
아닙니다. 직접 생성한 dataclass, 복사한 ID, 해시, `to_dict()` 결과 또는 미리보기는 검증이나 승인
권한이 아닙니다. 모든 consumer는 전체 등록 컨텍스트를 다시 검증해야 하며, 미리보기 builder는
diff 도출 전에 이를 수행합니다. 위조·오래된 상태·변경된 내용은 거부합니다.

## 등록된 manifest와 식별값

쌍 스키마 `1.0`, 레지스트리 버전 `owned-synthetic-v1` 및 내용 버전 `test-only-v1`은
S1의 빈 레지스트리, 리포트 스키마 `1.2`, 패키지 버전 `0.1.0a3`와 별개입니다.
manifest에는 정확히 `schema_version`, `kind`, `registry_version`, `content`, `review_binding`이
있으며 `kind`는 `owner-policy-repair-pair`입니다. 폐쇄형 전체 content는 다음과 같습니다.

| Content 필드   | 등록된 값 또는 binding                                                              |
| -------------- | ----------------------------------------------------------------------------------- |
| `version`      | `test-only-v1`                                                                      |
| `scenario_id`  | `synthetic-owner-omission-v1`                                                       |
| `path`         | `policy.py`, 표시용 데이터만 의미                                                   |
| `before`       | 정확히 `text` / `sha256`: 경고를 유지한, 의도적으로 잘못된 테스트 전용 비실행 소스  |
| `after`        | 정확히 `text` / `sha256`: 변경하지 않은 올바른 유지·관리 소스 `OWNER_POLICY_SOURCE` |
| `criteria`     | 정확히 `text` / `sha256`: 마지막 LF 없는 S1의 정확한 정책 전용 기준                 |
| `assumptions`  | S1의 정확한 신뢰 입력 가정 3개를 순서대로 포함; 각 항목은 `id` / `text`             |
| `cases`        | 검토한 정확한 순서의 8개 케이스/예상값 배열                                         |
| `cases_sha256` | 예상값을 포함한 전체 배열의 canonical 식별값                                        |

before와 after는 BOM 없는 UTF-8, LF 전용이며 마지막 LF를 유지합니다. before는 마지막
subject/owner 비교만 생략하고 의도적으로 잘못된 테스트 전용임을 명시한 경고를 앞에 붙입니다.
올바른 유지·관리 예제를 변경하거나 취약하다고 표시하지 않습니다. builder는 시나리오 slug나
after 해시만이 아니라 S1 요청 식별값과 전체 내용을 고정합니다.

| 내용 식별값         | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| Before, 2,016 bytes | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| After, 1,960 bytes  | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |
| 케이스/라벨 8개     | `96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3` |
| 전체 content        | `2cbbc004b46ac2bc65b98c3e3b4b3e1e5919dd3d1b35920871372432c23203fb` |
| 검토 기록           | `3540dd3578ee838b1bfb34f3c02019286716b47664ec942da46e8dac25d4b7e8` |

현재 pair ID는
`owner-repair-pair-a4f764f8cbff25089bd40076c5f4a5cc76775312c973e3e22e9b9f353038ba08`입니다.
이는 파생 속성이며 자기 참조 manifest 필드가 아닙니다. 구조화된 식별값은 객체 키 정렬,
compact 구분자, 배열 순서 유지, 마지막 LF 없는 canonical UTF-8 JSON을 사용합니다.
반면 소스/diff 해시는 정확한 UTF-8 텍스트 바이트를 식별합니다. 버전/내용이 변경되면 이전
binding은 무효화되며, 변경한 데이터의 해시를 다시 계산해도 이를 등록하거나 승인하지 않습니다.

### 별도 기록된 검토 binding

`review_binding`에는 정확히 `content_sha256`, `review_record_sha256`, `review_record`가
있습니다. 전체 기록은 manifest에 포함되어 출력되며 별도 파일에서 읽어 오지 않습니다.
이 기록은 content·cases 해시를 설계 head `35ebe17d96c07540cf2753f2e53625d138ded0aa`,
결정 날짜 `2026-10-19`, 결정 `accept-scenario-and-case-expectations` 및 위의 결정 기록 URL에
결합합니다. 나머지 폐쇄형 필드는 `schema_version` = `1.0`,
`kind` = `recorded-owner-policy-pair-review`와 정확히
`provenance` = `{"kind":"recorded-maintainer-chat","authenticated":false}`입니다.

content를 먼저 해시하고 별도 기록이 그 content 해시를 참조하며, manifest가 두 해시에
결합합니다. 자기 참조 해시 순환은 없습니다. validator는 URL이나 복사한 digest만이 아니라
등록된 전체 기록을 확인합니다. 기록한 관리자 결정은 정확한 검토의 실제 출처이지만 JSON 자체는
인증된 승인 증표나 다른 행동에 이전할 수 있는 권한이 아닙니다.

### 예상값은 관찰이 아님

| Case ID                        | 검토된 예상값 |
| ------------------------------ | ------------- |
| `owner-control`                | `allow`       |
| `non-owner`                    | `deny`        |
| `missing-read-scope`           | `deny`        |
| `unauthenticated-owner`        | `deny`        |
| `missing-principal`            | `deny`        |
| `missing-report`               | `deny`        |
| `wildcard-is-not-read`         | `deny`        |
| `exact-owner-no-normalization` | `deny`        |

전체 principal/report 입력은 manifest에 보이며 subject `" alice"`의 앞쪽 공백은 의미가
있습니다. 과거 설계의 정적 가설은 변경 전후 결과가 아닙니다. 실제 관찰은 null, 비교는
`not-evaluated`, 인가는 `unknown`을 유지합니다. 이 예상값 8개는 과거 #77 예상값 10개나
별도의 개발자 테스트 라벨 28개를 대체하지 않습니다. 유한한 합성 예상값은 신뢰할 수 있는
인증이나 HTTP 강제를 증명하지 않습니다.

## 출력 전용 diff 미리보기

미리보기 `kind`는 `owner-policy-repair-pair-preview`입니다. `schema_version`, `pair_id`,
전체 재검증한 `pair`, `recipe_version`, `diff`, `diff_sha256` 및 아래 사실을 포함합니다.
recipe `unified-v1-context-3`은 등록된 정확한 소스 바이트에서 문맥 3줄과 고정 표시 header
`a/policy.py` / `b/policy.py`를 사용해 diff를 도출합니다. 모델 제공 diff를 받지 않습니다.
현재 정확한 diff 해시는
`0358127d2373c7a729c0b656c1c9cbcb698dc5f04073a917f848280d0c8be75d`입니다.

| Host 소유 필드                                                  | 값                                                                      |
| --------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `provider_calls`                                                | `0`                                                                     |
| `execution_status` / `patch_application` / `restoration_status` | `not-run`                                                               |
| `observations`                                                  | 정확히 `{"before":null,"after":null}`                                   |
| `comparison_status`                                             | `not-evaluated`                                                         |
| `authorization_status`                                          | `unknown`                                                               |
| `provenance`                                                    | 정확히 `{"kind":"registered-test-only-template","authenticated":false}` |

미리보기는 확인 가능한 데이터이며 승인 token, renderer, 패치 서비스 또는 실행 계획이 아닙니다.
이를 표시해도 diff를 적용하거나 정책을 검증하지 않습니다. 이후 표현 계층에서 텍스트를 escape하며,
복사한 JSON·터미널 출력·Markdown은 권한을 부여할 수 없습니다.

## 제한과 엄격한 검증

공유 decoder는 전체 host 미리보기 metadata와 diff를 포함해 canonical/raw UTF-8 262,144바이트,
깊이 32, 방문 node 8,192개 예산을 강제합니다. 등록 소스 텍스트는 32,768자, 일반 텍스트는
4,096자, 식별자는 128자로 제한합니다. 고정 계약에는 가정 3개, 서로 다른 case ID 8개와
principal당 최대 16개의 서로 다른 scope가 있습니다. 이 제한이 레지스트리를 설정 가능하게
만들지는 않으며, 형식이 올바른 다른 내용도 거부합니다.

정확한 키/스칼라 타입, 중복 JSON 키, 유한하지 않은 숫자, 잘못된 Unicode 및 공유 텍스트 제어
규칙을 강제 변환이나 소스 정규화 없이 검사합니다. 알 수 없는/추가 필드, 변경한 라벨/소스/기준/
가정/버전/검토 출처, 위조 해시 및 실행·제공자·패치·승인 필드는 거부합니다. 등록 manifest를
재구성한 뒤 전체 컨텍스트 일치가 필요하며, wrapper를 직접 생성해도 검사를 우회하지 못합니다.

## 순수 Python 미리보기 예제

alpha.3 실행 파일이 아닌 이 브랜치의 소스 환경을 사용합니다. 이 예제는 비실행 등록 데이터를
구성하고 ASCII escape한 JSON만 출력합니다. AI 응답을 받거나 어느 정책 후보도 평가하거나
승인·파일시스템/네트워크·패치 요청을 하지 않습니다.

```python
import json

from authzest.codex.owner_policy_repair_pair import (
    build_owner_policy_repair_pair,
    prepare_owner_policy_repair_pair_preview,
)

pair = build_owner_policy_repair_pair()
preview = prepare_owner_policy_repair_pair_preview(pair)
print(json.dumps(preview.to_dict(), ensure_ascii=True, indent=2))
```

## 남은 gate

오프라인 검증은 정확한 binding, 분리된/위조/오래된 산출물, 엄격한 폐쇄형 구조, 전체 미리보기
예산 및 부수 효과나 대상 import/평가를 막는 guard를 다뤄야 합니다. 이 문서는 요구사항을
기록하며 테스트/CI 통과나 런타임 관찰을 기록하지 않습니다.

모델 통합에는 별도로 최소화한 요청/출력 설계와 새롭고 제한된 공유 결정이 필요합니다.
변경 전후 관찰에는 별도로 검토한 고정 recipe와 새로운 정확한 계획별 실행 결정이 필요하며,
#80은 이 잘못된 소스를 계속 거부해야 합니다. pair-bound 새 복사본의 diff 승인·적용·검증·복구는
각각 별도 후속 설계와 현재 상태 기반 결정을 받아야 합니다. 이 데이터 API나 기록된 라벨 승인은
런타임, 제공자 사용, 소스 공유, 파일 쓰기, 자동 재시도/복구, 병합, tag 또는 release를
허용하지 않습니다. 더 넓은 #81/#82 및 잔여 도구/출판 gate는 독립적으로 유지하며 미완료입니다.
