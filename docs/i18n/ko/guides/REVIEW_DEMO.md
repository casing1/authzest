<p align="center">
  <a href="../../../guides/REVIEW_DEMO.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 통합 검토 시연

[문서 목차](../INDEX.md) · [소스 선언 비교](PROPOSAL_CHECK.md) · [Fixture 적용 시연](FIXTURE_DEMO.md)

## 범위와 제공 상태

[#71](https://github.com/casing1/authzest/issues/71)은 alpha.3 이후 소스 checkout에
`authzest review-demo`를 추가합니다. 이 변경을 포함한 소스 revision을 사용하세요.
공개 alpha.3 바이너리에는 명령이 없습니다. 패키지 버전 `0.1.0a3`, scan report schema `1.2`와
기존 산출물 스키마는 그대로입니다. 완료 조건과 병합 상태는 이슈에서 추적하며 새 릴리스가 아닙니다.

읽기 전용 명령으로 패키지에 포함한 예제 하나의 정확한 diff·연결된 근거·기대값·소스 선언 비교와
실행할 수 없는 방어적 회귀 테스트 초안을 함께 표시합니다. 기능의 모든 데이터를 메모리에서 만들며
입력 파일·임시 디렉터리·제공자 호출·자식 프로세스·대상 import나 실행·패치 적용·산출물 쓰기가 없습니다.
Windows를 포함해 POSIX 파일 reader를 요구하지 않습니다. 기존 Codex·fixture 적용·검증·복구
흐름은 변경하지 않습니다.

## 시연 실행

소스 [개발 환경](../README.md#개발-환경)을 활성화한 상태에서 실행합니다.

```bash
authzest review-demo --help
authzest review-demo
authzest review-demo --json
```

`--json`과 도움말만 받습니다. 위치 인자나 대상·입력·모델·적용·런타임·승인·내보내기 옵션은
없으며 확인 질문도 하지 않습니다. 텍스트 출력은 미리보기·비교·초안·한계를 표시하고 JSON에도
동일한 통합 정보가 담깁니다. 출력은 ASCII 이스케이프를 사용합니다.

유지하는 소스 전용 사례는 `Security` 선언 하나의 `scopes=[]`를 `scopes=["reports:read"]`로
변경하며 유효 의존성 개수는 하나로 유지합니다. 따라서 선언 목표 두 개는 `matched`이고
호출자가 작성한 제한 정책 의도 하나는 `not-evaluated`입니다. helper는 인증 구현이 아닌
소스 전용 placeholder라고 명시되어 있으며 예제를 import하거나 실행하지 않습니다.
mock 제안·검토 산출물이지 모델 출력이나 올바른 접근 허용·거절을 입증하는 시연이 아닙니다.

## 세 영역을 구분해서 읽기

- `preview`는 정확한 diff·소스/정책 참조·예상 결과와 draft/not-run 상태를 유지합니다.
- `comparison`에는 기존 소스 전용 `matched`, `mismatched`, `unknown`, `not-evaluated` 결과를
  담습니다. 제공한 snapshot을 비교하며 디스크/Git 최신성이나 런타임 인가를 확인하지 않습니다.
- `regression_test_draft`는 `structured-prose`, `status: draft`, `executable: false`이며
  출처는 `maintainer-authored-template`입니다. 목적·참조·계획한 관찰·기대값·한계를 설명하고
  관찰은 null, 검증은 not-run으로 남깁니다.

초안은 실행 가능한 테스트 코드나 shell/HTTP 절차가 아닙니다. 선언 비교 결과를 런타임 관찰에
복사하거나 테스트 통과를 주장하지 않습니다. bundle·요청·검토·제안·manifest·소스 식별값과
변경 전후 해시를 통해 제공한 산출물에 연결하며 연결된 내용이 바뀌면 초안 자체의 식별값도
바뀝니다. 어떤 식별값도 동의 신원을 인증하거나 공유·적용·검증·복구를 허가하지 않습니다.
정책 인용만으로 정책의 정확성을, scope 선언만으로 강제 적용을 입증할 수 없습니다.

최상위 `status: completed`와 종료 `0`은 통합 처리가 끝났다는 뜻이지 보안이나 테스트 통과가
아닙니다. 적용은 false, 검증·런타임 검증은 not-run, 인가는 unknown을 유지합니다.
잘못된 인자·옵션은 `2`, 잘못된 내장 산출물을 포함한 내부 실패는 `1`, 중단은 `130`으로
종료합니다. 잘못된 입력 bundle로 분류할 사용자 산출물을 받는 명령이 아닙니다.

## Python API와 출처

```python
from authzest.codex.review_demo import build_review_demo_bundle
from authzest.runner.review_demo import compose_review, run_review_demo

bundle = build_review_demo_bundle()
review = compose_review(bundle)
demo = run_review_demo()
```

`compose_review`는 기존의 검증된 preview bundle도 받아 내용을 다시 검증하고 내부 경로를
읽지 않은 채 분리된 데이터를 반환합니다. 모든 입력을 mock으로 표시하지 않고 제공한 소스
산출물의 식별값과 출처를 보존합니다. `live_provider_calls: 0`은 이번 통합 과정만 설명하며
제공된 산출물에 기록된 과거 제공자 사용량이 0이라는 뜻이 아닙니다. 초안 템플릿 출처는
검토·모델 출처와 별개입니다. 잘못된 산출물은 `ContractError`를 발생시킵니다.

`run_review_demo()`는 인자를 받지 않고 고정 사례를 `scope-declaration-review`,
산출물을 caller-authored-mock, `simulated_draft: true`로 표시합니다. 두 API 모두 제공자를 호출하거나
제안을 적용하거나 테스트를 실행하지 않습니다. 실행 가능한 회귀 테스트 생성, 더 넓은 수정
흐름과의 승인된 연동 및 #35 전체 완료 조건은 별도 작업입니다.
