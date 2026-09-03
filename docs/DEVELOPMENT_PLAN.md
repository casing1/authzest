# AuthZest Development Plan

## 개발 방향

AuthZest는 먼저 결정론적인 정적 분석 도구를 만들고, 그 결과를 보강하는 선택 기능으로 Codex를
연결합니다. AI가 없어도 같은 입력에서 같은 결과를 내고, 각 판단을 소스 위치로 설명할 수 있어야
합니다.

진행 상황의 공개 기준은 [roadmap issue #1](https://github.com/casing1/authzest/issues/1)입니다.
아래 단계의 항목은 구현 전에 더 작은 issue와 명확한 완료 조건으로 나눕니다.

## Phase 1 — 분석 범위 고정

- [ ] 지원할 FastAPI 버전과 Python 구문 범위를 정합니다.
- [ ] authentication과 authorization의 판정 기준을 구분합니다.
- [ ] 지원하지 않는 동적 패턴과 false-positive 처리 원칙을 적습니다.
- [ ] 안전한 예제와 취약한 예제를 포함한 작은 fixture 애플리케이션을 만듭니다.
- [ ] report model과 CLI exit code의 공개 계약을 정합니다.

완료 기준: 지원 범위와 한계가 테스트 fixture로 표현되고 report schema가 테스트로 고정됩니다.

## Phase 2 — FastAPI 접근통제 탐색

- [ ] `APIRouter` prefix와 `include_router` 구성을 해석합니다.
- [ ] 애플리케이션, router, route와 함수 parameter의 `Depends`를 수집합니다.
- [ ] FastAPI `Security`와 security scheme 사용을 수집합니다.
- [ ] route를 `protected`, `unprotected`, `unknown`으로 분류합니다.
- [ ] 모든 분류에 파일, 줄 번호와 탐지 근거를 포함합니다.

완료 기준: fixture의 endpoint별 기대 분류와 실제 결과가 모두 일치합니다.

## Phase 3 — Finding engine

- [ ] 인증 누락과 같은 고신뢰 finding부터 규칙을 추가합니다.
- [ ] severity와 confidence를 분리합니다.
- [ ] 오탐을 숨길 수 있는 suppression 형식과 사유 기록을 추가합니다.
- [ ] 사람이 읽는 출력과 안정적인 JSON 출력을 함께 제공합니다.
- [ ] 분석 실패를 취약점으로 잘못 보고하지 않도록 unknown 상태를 유지합니다.

완료 기준: finding마다 검출 fixture, 비검출 fixture와 source evidence가 존재합니다.

## Phase 4 — 안전한 테스트 실행

- [ ] 기본 동작은 요청을 보내지 않는 test plan 생성으로 제한합니다.
- [ ] HTTP 실행은 명시적인 opt-in 옵션 뒤에 둡니다.
- [ ] 초기 실행 대상은 localhost와 사용자가 허용한 주소로 제한합니다.
- [ ] timeout, 요청 수 제한과 결과 재현 정보를 기록합니다.
- [ ] 파괴적인 method와 실제 데이터 변경 가능성을 별도로 통제합니다.

완료 기준: 동의하지 않은 네트워크 요청이 발생하지 않으며 실행 결과를 재현할 수 있습니다.

## Phase 5 — 선택적 Codex adapter

- [ ] mock adapter로 interface와 failure behavior를 먼저 고정합니다.
- [ ] Codex CLI adapter를 timeout과 명시적 opt-in 뒤에 추가합니다.
- [ ] App Server adapter의 인증 및 승인 흐름을 별도로 검토합니다.
- [ ] 전송 전 secret과 개인정보 redaction 정책을 적용합니다.
- [ ] Codex 사용 불가 또는 실패 시 결정론적 분석 결과를 그대로 유지합니다.

완료 기준: Codex 연동을 제거해도 core, CLI와 테스트가 정상 동작합니다.

## Phase 6 — 릴리스 준비

- [ ] end-to-end fixture 검사를 CI에 추가합니다.
- [ ] 지원 범위, 알려진 한계와 보안 모델을 문서화합니다.
- [ ] semantic versioning과 changelog 규칙을 적용합니다.
- [ ] 태그 기반 바이너리와 checksum 배포를 검증합니다.
- [ ] 첫 번째 공개 pre-release를 만들고 설치 과정을 새 환경에서 검증합니다.

## 작업별 체크리스트

### 시작 전

- [ ] 연결된 issue와 명확한 완료 조건이 있습니다.
- [ ] 작업 범위가 한 PR에 검토 가능한 크기입니다.
- [ ] 최신 `main`에서 규칙에 맞는 브랜치를 만들었습니다.
- [ ] 보안상 민감한 데이터나 실제 서비스 요청이 필요한지 확인했습니다.

### 구현 중

- [ ] 모듈 경계를 유지하고 core에 UI 또는 provider 의존성을 넣지 않았습니다.
- [ ] 정상, 경계, 실패 사례를 테스트로 표현했습니다.
- [ ] finding은 소스 근거를 제공하고 unknown과 vulnerable을 구분합니다.
- [ ] 관련 없는 포맷 변경이나 리팩터링을 섞지 않았습니다.

### PR 전

- [ ] 커밋이 한 가지 논리적 변경을 설명합니다.
- [ ] Python과 frontend의 관련 검사가 통과합니다.
- [ ] 생성 파일, secret과 개인정보가 diff에 없습니다.
- [ ] PR에 검증 방법, 보안 영향과 연결 issue를 적었습니다.
- [ ] CI가 통과한 뒤 merge하고 브랜치를 삭제합니다.
