<p align="center">
  <a href="../../../guides/PROPOSAL_CHECK.md">English</a> ·
  <strong>한국어</strong>
</p>

# 소스 전용 제안 선언 검사

[문서 목차](../INDEX.md) · [제안 미리보기](PROPOSAL_PREVIEW.md) · [예상 결과 계약](../reference/EXPECTATION_CONTRACT.md)

## 범위와 제공 상태

[#69](https://github.com/casing1/authzest/issues/69)는 alpha.3 이후 소스 checkout에
`authzest proposal-check`를 추가합니다. 이 변경을 포함한 소스 revision을 사용하세요.
공개 alpha.3 바이너리에는 이 명령이 없습니다. 패키지 버전 `0.1.0a3`, scan report schema `1.2`와
기존 제안·예상 결과·preview bundle 스키마는 그대로이며 새 릴리스가 아닙니다.

명령은 `proposal-preview`와 같은 검증된 오프라인 bundle을 읽은 뒤 지원하는 선언 기대값을
기준·제안 소스 문자열과 비교합니다. 해당 문자열을 import·실행하거나 Codex를 호출하거나 worker를
시작하지 않습니다. bundle 내부 경로·Git·현재 소스 파일을 읽거나 패치를 적용하거나 승인을 부여하지도
않습니다. 제공된 snapshot을 비교할 뿐 디스크 최신성·정책 강제 적용·런타임 인가를 검사하지
않으며 기존 고정 fixture 흐름은 변경하지 않습니다.

## 명령 사용

지원하는 POSIX 시스템에서 [개발 환경](../README.md#개발-환경)을 활성화하고 저장소 루트에서 실행합니다.

```bash
preview_dir=$(mktemp -d)
python -m scripts.demo_preview --output "$preview_dir/bundle.json"
authzest proposal-check "$preview_dir/bundle.json"
authzest proposal-check "$preview_dir/bundle.json" --json
```

기존 exporter는 호출자가 작성한 공개 의도 예제를 만듭니다. 해당 `policy-intent` 기대값은
**`not-evaluated`**이며 인가 검사가 일치했다는 뜻이 아닙니다. 모델을 호출하거나 fixture를
변경하지 않습니다. exporter는 새 출력 파일만 배타적으로 생성하고 검사 명령 자체는 읽기
전용입니다. 두 명령 모두 선택한 bundle을 확인할 수 있도록 남깁니다.

선언 비교에는 기존 예상 결과·제안 API를 사용해 검토한 소스 snapshot과 명시적인
`dependency-declarations` 또는 `scope-declarations` 목표를 묶으세요. 예를 들어 `{"count": 1}`은
선언 개수 목표이고 `{"scopes": ["items:read"]}`는 scope 선언 목표입니다. 근거 참조와 해시는 같은
요청·정확한 제안에서 도출해야 하며 관련 없는 산출물에서 수동 복사하면 안 됩니다. 목표가 있다는
사실만으로 인용 정책이 이를 뒷받침한다고 입증하지는 않습니다.
[manifest API](../reference/EXPECTATION_CONTRACT.md#python-api와-오프라인-검사)를 참고하세요.

## 초기 지원 범위

구조적으로 유효한 bundle도 비교 지원 범위를 벗어날 수 있습니다. 처음에는 선택한 소스가 정확히
하나이고 변경 파일도 하나여야 합니다. 기준 라우트 근거는 해당 소스 재파싱 결과와 완전히 일치해야
하며 유효한 참조 ID만으로는 부족합니다. 두 snapshot 모두 별칭·라우터 없이 단일 `FastAPI`
소유 객체에 직접 등록한 지원 범위 내 모듈 수준 라우트를 사용해야 합니다.
일반 `scan` 파서의 지원 구문보다 좁은 범위입니다.
`pkg/api.py` 같은 소스 경로 표기는 Windows를 포함한 모든 운영체제에서 bundle 계약의 POSIX
형식을 사용합니다. 이 정규화는 기존 scan 표시 경로나 등록 식별값을 바꾸지 않습니다.
정식 이름의 `from fastapi import FastAPI, Depends, Security`, `typing` 또는 `typing_extensions`의
`Annotated`/`Any`, 지원하는 기본·generic·union annotation, 명시적인 의존성 참조와 리터럴
보조 인자를 지원합니다. namespace import, 사용자 정의 import/decorator와 문자열·타입 별칭은
지원하지 않습니다. 각 소스 snapshot은 32,768자 이하이며 기준 분석은 진단·파싱 오류 없는
`bounded`여야 합니다.

여러 파일, 별칭, router/include 연결, 동적·조건부 선언, 지연 등록, 부분 근거나 모호한 라우트
대응은 추측하지 않습니다. 이름 변경·삭제된 라우트와 지원하지 않는 소스의 선언 비교는 `unknown`이며
인가 성공·실패 판정이 아닙니다. 기준 등록 ID는 소스 위치를 포함하므로 편집 후에도 같다고
가정하지 않습니다. 결과는 소스 해시·근거·등록 식별값을 유지해 선택한 변경 전후 관찰을
검토할 수 있게 합니다.
`before_observed`와 `observed`는 각각 기준·제안의 선언 값이며 후자를 `expected`와 비교합니다.
`unknown` 또는 `not-evaluated`에서는 두 관찰과 `after_registration_id`가 `null`입니다.
기준 관찰을 편집 후 측정값으로 표시하지 않습니다.

| 예상 결과                 | 비교하는 소스 관찰                                  | 의미와 한계                                                                            |
| ------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `dependency-declarations` | 유효 의존성 선언 개수                               | 일반 `Depends` 선언도 셉니다. 개수는 인증이나 인가를 입증하지 않습니다.                |
| `scope-declarations`      | 유효 `Security` 선언에서 고유하게 모아 정렬한 scope | scope 선언은 강제 적용이 아닙니다. 미해석 scope 정보를 빈 집합으로 간주하지 않습니다.  |
| `policy-intent`           | 없음. 항상 `not-evaluated`                          | 공개·제한 의도는 호출자가 작성한 정책 해석이며 이 검사기가 소스에서 추론하지 않습니다. |

소스 비교는 기대값·변경 전후 관찰·이유와 함께 `matched`, `mismatched`, `unknown`을 보고하며
정책 의도는 `not-evaluated`로 표시합니다. 불일치는 제공한 선언 목표와 다르다는 뜻이지 발견한
취약점이 아닙니다. 의존성 0개나 빈 scope 집합만으로 endpoint를 공개·안전·취약하다고 분류하지 않습니다.

## 결과·종료 코드·입력 처리

`status: completed`와 종료 `0`은 비교 처리가 끝났다는 뜻이며 결과에 `mismatched`, `unknown`,
`not-evaluated`가 있어도 같습니다. 전체 일치 요약이나 보안 통과가 아니므로 개별 결과를 확인하세요.
런타임 검증은 `not-run`, 인가는 `unknown`, 적용은 `false`, 제공자 호출은 0회를 유지합니다.
기존 미리보기 API는 계속 draft/not-run 데이터를 반환하며 비교 결과는 승인 증표나 실행 계획이 아닙니다.

CLI는 [제안 미리보기](PROPOSAL_PREVIEW.md#파일-처리와-실패)와 같은 제한된 reader를 사용합니다.
전체 최대 256 KiB의 안정적인 UTF-8 일반 JSON 파일 하나만 읽고 중복 키·중첩 계약을 검증합니다.
마지막 경로 요소의 symlink, 특수 파일, 감지한 변경, 잘못된 입력이나 불일치하는 산출물 연결은
거절합니다. 내부 소스 경로는 읽지 않습니다. Windows 등 파일 reader 미지원 플랫폼에서는
파일을 열기 전에 거절하며 순수 메모리 API는 플랫폼 독립적입니다. 상위 디렉터리 symlink나
적대적인 동시 쓰기를 완전히 배제하지 않으며 바이트 한도는 파일시스템 접근 시간 제한이 아닙니다.
직접 관리하는 파일과 디렉터리를 사용하세요.

잘못된 입력은 `2`, 예상하지 못한 처리 실패는 `1`, 중단은 `130`으로 종료합니다. 유효하지만
지원하지 않는 소스는 잘못된 JSON이 아닌 `unknown` 결과를 만듭니다. 제공자·적용·실행·승인
옵션은 추가하지 않습니다. 로컬 출력에는 선택한 소스나 정책 데이터가 포함될 수 있으므로
공개하거나 공유 로그로 보내기 전에 확인하세요.

## Python API

이 예제는 기존 `request`, 검증된 `review`, 정확한 `proposal`과 해당 요청에서 검토한
소스·라우트·정책 근거 ID가 있다고 가정합니다. 명시적인 선언 목표를 제공하며 일치 결과는
위의 지원 구문·근거 검사 조건을 충족해야 합니다.

```python
from authzest.codex.expectations import prepare_expectation_manifest
from authzest.codex.preview import prepare_preview_bundle
from authzest.runner.proposal_check import check_proposal

manifest = prepare_expectation_manifest(
    request,
    review,
    proposal,
    expectations=[
        {
            "id": "one-declaration",
            "source_evidence_id": source_evidence_id,
            "route_evidence_id": route_evidence_id,
            "policy_evidence_ids": [policy_evidence_id],
            "observation": "dependency-declarations",
            "expected": {"count": 1},
            "limitations": ["Declaration count does not establish access control."],
        }
    ],
)
bundle = prepare_preview_bundle(request, review, proposal, manifest)
result = check_proposal(bundle)
```

`check_proposal`은 `ValidatedPreviewBundle` wrapper도 다시 검증합니다. 별도의 편의 API인
`authzest.runner.proposal_check.load_check(Path("bundle.json"))`는 같은 제한된 reader로
명시적으로 선택한 파일만 읽습니다(`Path`는 `pathlib`에서 import).

순수 `check_proposal` 경로는 제공된 문자열을 데이터로 파싱해 분리된 비교 결과를 만듭니다.
파일 읽기·쓰기, 프로세스 시작, 제안 애플리케이션 import나 제공자 사용은 하지 않습니다.
이 제한적 정적 비교는 생성 회귀 테스트·일반 저장소 수정·런타임 인가 검사나 #35 전체 흐름을
구현한 것이 아닙니다.
