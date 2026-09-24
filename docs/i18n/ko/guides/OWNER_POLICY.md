<p align="center">
  <a href="../../../guides/OWNER_POLICY.md">English</a>
  · <strong>한국어</strong>
</p>

# 소유 보고서 정책 예제

[문서 목차](../INDEX.md) · [소스 전용 예제](EXAMPLES.md) · [통합 검토 시연](REVIEW_DEMO.md)

## 범위와 제공 상태

[#73](https://github.com/casing1/authzest/issues/73)은 소유자 전용 보고서 읽기 정책 하나와
독립적인 회귀 행렬을 소스 checkout에 추가합니다. 개발자용 예제이지 새로운 AuthZest 명령이나
런타임 모드가 아닙니다. 변경을 포함한 checkout에서 [개발 환경](../README.md#개발-환경)을
활성화하세요. 공개 alpha.3 바이너리는 예제나 테스트를 설치하지 않으며 패키지 `0.1.0a3`와
scan report schema `1.2`도 그대로입니다. 완료 조건과 정책 검토 상태는 이슈에서 기록하며
이 안내는 새 릴리스를 주장하지 않습니다.

예제는 개발용 단위 테스트로 실행하는 순수 정책 함수, 대상 실행 없이 목록화하는 FastAPI 선언,
아직 구현·검사하지 않은 실제 인증·HTTP 연동을 구분합니다. 데이터는 가상이며 취약 버전·우회
시연·외부 서비스·모델 호출·생성 코드 실행은 포함하지 않습니다.

## 정책과 신뢰 경계

[정책 모듈](../../../../examples/fastapi_owner_policy/policy.py)은
`Principal(subject, authenticated, scopes)`, `Report(report_id, owner_id)`,
`can_read_report(principal, report) -> bool`을 정의합니다. 다음 조건을 모두 만족해야 허용합니다.

- 입력이 정확한 `Principal`·`Report` 타입이며 ID는 유효한 비공백 문자열이어야 합니다.
- `authenticated`가 정확히 `True`여야 합니다.
- `scopes`는 비공백 문자열의 `frozenset`이고 정확한 scope `reports:read`를 포함해야 합니다.
- principal의 subject와 보고서의 비공백 owner ID가 정확히 같아야 합니다.

나머지는 모두 거절하며 신원·소유자 누락, scope 누락과 비소유자 접근도 포함합니다.
공백 검사는 빈 ID·scope를 거절할 뿐 비교 값을 정규화하지 않습니다. admin·와일드카드·부분 문자열·
대소문자 무시 예외가 없으며 필요한 scope가 포함됐어도 scope 모음 자체가 잘못되면 허용하지 않습니다.

함수는 신뢰하는 호출자가 검증된 principal 속성과 신뢰할 수 있는 보고서 소유 정보를 준다고
가정합니다. 사람 인증·토큰 검증·데이터베이스 소유 정보 조회를 하거나 클라이언트가 제공한 신원·scope를
신뢰할 수 있게 만들지 않습니다. 테스트에서 `Principal`을 만드는 것은 이 신뢰 입력을 모형화한 것이지
인증 구현이나 해당 필드를 HTTP에서 그대로 받아도 된다는 뜻이 아닙니다.

## 두 종류의 검사 실행

저장소 루트에서 실행합니다.

```bash
authzest scan examples/fastapi_owner_policy --json
python -m pytest tests/test_owner_policy.py
```

scan은 Python 파일 두 개를 읽고 `GET /reports/{report_id}` 등록 하나를 목록화합니다.
분석은 bounded, 진단·파싱 오류는 없으며 Codex는 비활성입니다. `require_authenticated_principal`을
대상으로 하는 parameter-annotation `Security` 선언과 `scopes=["reports:read"]`를 기록하며
직접·유효 의존성 목록에 각각 해당 선언 하나가 있습니다. 정적 소스 사실이지 정책 함수를
올바르게 호출하거나 HTTP 접근을 강제한다는 증거가 아닙니다.

개발용 테스트는 검토 대상인 저장소 소유 **순수 정책 모듈**을 의도적으로 import·호출하여
[독립 행렬](../../../../tests/fixtures/owner_policy/cases.json)과 비교합니다. 예상 허용·거절 값은
테스트 대상 함수로 계산하지 않는 데이터입니다. 인증·scope·소유자 조건과 잘못되거나 누락된 입력을
다룹니다. 별도 목록화 회귀 검사는 애플리케이션·프레임워크를 import하지 않고 소스 근거를 확인합니다.
이 검사들에서 FastAPI 애플리케이션·endpoint·인증 제공자를 실행하지 않습니다.
단위 테스트 실행은 AuthZest fixture 실행기의 허가가 아닙니다.

행렬 통과는 나열한 정책 입력과 구현에 관한 근거만 제공합니다. scan 성공은 목록을 생성했다는
뜻입니다. 어느 쪽도 일반 인가 판정·endpoint 테스트·취약점 finding·모델 품질 평가나 검증된 보안
수정이 아닙니다.

## 소스 참조와 의도적으로 제외한 연동

[main.py](../../../../examples/fastapi_owner_policy/main.py)는 소스 전용 FastAPI 참조입니다.
인증 제공자는 의도적으로 미설정·기본 거절 상태이며 신원·인증 플래그·scope를 요청 필드에서
직접 받지 않습니다. 소스에는 고정된 가상 보고서 조회와 데이터 반환 전 정책 결정이 있지만
실행 가능한 인증 튜토리얼은 아닙니다. 이번 검증에서 서버를 시작하거나 모듈을 import하지 마세요.

실제 principal 검증·HTTP endpoint 동작·데이터베이스 소유 정보·토큰 만료·Codex 패치 제안 연동은
별도 작업입니다. opt-in [읽기 전용 Codex 소유 정책 검토](CODEX_OWNER_REVIEW.md)는 패키지
snapshot으로 검토·사례 초안만 만들고 이 예제를 실행하지 않습니다.
scanner는 정책 함수의 의미를 추론하지 않습니다. 이 예제는 `proposal-check`의
좁은 지원 구문, 기존 복사본 적용 흐름이나 고정 소스·런타임 fixture 허용 목록을 확대하지 않습니다.
기본 scan은 소스 전용을 유지하며 제공자·계정 사용·소스 공유·자동 패치 적용은 없습니다.

## 행렬 출처와 호환성

관리자는 2026-09-24에 인증된 신원·정확한 `reports:read` scope·소유자 일치를 모두 요구하고
관리자 예외 없이 정보가 없으면 거절하는 정책 기준을 승인했습니다. 정책 행렬과 정확한 예상값
28개는 계속 assistant 작성 개발 자료이며 사람이 작성했거나 독립적으로 승인한 정답 label은
아닙니다. 기록한 상태는 `criteria-approved-label-review-pending`이며 label 전체 승인이 아닙니다.
정책 결정과 관리자 검토는 [#73](https://github.com/casing1/authzest/issues/73)과
[#75](https://github.com/casing1/authzest/issues/75)에서 추적합니다. 같은 로직에서 구현과 예상값을
함께 도출하지 말고 예상값을 구현 변경과 별도로 검토하세요. 정책 승인은 소스 공유·계정 사용·
패치 적용·실행을 승인하지 않습니다.

고정된 `tests/fixtures/ai_evaluation/v1` corpus·label·held-out 분리·해시는 그대로입니다.
기존 소스 전용 scope 선언 예제의 인가는 계속 unknown이며 새 정책 단위 테스트로 판정을
격상하거나 mock 평가 점수를 바꾸지 않습니다. 기존 Codex·fixture 흐름, 공개 alpha.3 산출물과
더 넓은 #35의 미완료 상태도 유지합니다.
