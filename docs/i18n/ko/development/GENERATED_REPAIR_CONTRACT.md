<p align="center">
  <a href="../../../development/GENERATED_REPAIR_CONTRACT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 계약과 선택형 Codex 요청

[문서 목차](../INDEX.md)

## 상태 — 2026-11-09 KST

[#151](https://github.com/casing1/authzest/issues/151)은 [과목 릴리스 범위](https://github.com/casing1/authzest/issues/150)의 오프라인 요청·제안 계약을 선택형 `codex-generate` 어댑터 흐름에 연결합니다. 이번 변경은 오프라인/mock 테스트로만 검증하며 생성 수용 검증에 실제 계정·Codex 프로세스·모델을 사용하지 않았습니다. 실제 제공자/스키마 호환성과 진짜 생성 수용은 미검증이므로 #151은 열린 상태입니다. 기존 등록 템플릿의 수용 결과는 새로 작성한 수정안의 수용 결과가 아닙니다.

순수 계약과 preview-only 경로는 Codex를 시작하지 않습니다. 활성 흐름은 고정 사례에 대해 별도 승인한 요청 1회를 수행할 수 있지만 임의 저장소 입력, 소스 복사본 생성, 패치 적용, 생성 코드 실행, 파일 복구는 하지 않습니다. #152/#153의 검증/UI는 이번에 구현하지 않습니다. 기존 제품·리포트 버전과 Codex 고정 버전은 바뀌지 않으며 새 명령은 모델을 명시해야 합니다.

## 오프라인 입력 미리보기

이 변경을 포함한 소스 체크아웃을 설치한 환경에서 다음 명령은 고정 요청을 전송하지 않고 표시합니다.

```bash
authzest generation-preview
authzest generation-preview --json
```

기본 출력은 생성하지 않는다는 안내와 함께 전체 프롬프트·응답 스키마를 표시합니다. JSON 모드는 `status: "preview-only"`, `model_invoked: false`, `applied: false`, `execution_status: "not-run"`인 `generated-repair-request-preview` 문서 하나를 출력합니다. 모델·저장소 경로·실행 옵션은 없습니다. 이는 입력 미리보기이지 생성된 제안이나 실제 생성 흐름이 아닙니다.

## 선택형 요청 흐름

`codex-generate`는 `--model`을 필수로 받습니다. 선택 옵션 `--timeout-seconds`의 기본값은 120이며 0보다 크고 120 이하여야 합니다. 다음 명령은 플랫폼에 독립적인 완전한 오프라인 공유 미리보기만 표시합니다. 실제 요청을 검토할 때는 `EXPLICIT_MODEL`을 의도한 정확한 식별자로 바꾸세요.

```bash
authzest codex-generate --model EXPLICIT_MODEL --timeout-seconds 120 --preview-only
authzest codex-generate --model EXPLICIT_MODEL --timeout-seconds 120 --preview-only --json
```

`--preview-only`가 없으면 POSIX 활성 경로에서 유지하는 소스·정책·선언, 호스트 프롬프트와 출력 스키마를 먼저 정확히 표시하고 새 요청에 연결된 공유 확인을 요구합니다. 거절·취소·잘못된 확인은 공유 승인이 아닙니다. 미리보기도 동의가 아닙니다. 신뢰하는 로컬 Codex `0.153.0` 설치와 기존 ChatGPT 로그인을 사용하며 Codex는 자체 harness 문맥을 추가합니다.

승인한 요청은 AuthZest 재시도나 모델 대체 없이 어댑터 1회만 시도합니다. 요청 제한 시간은 최대 120초이고 정리는 별도로 처리하므로 전체 흐름의 절대 시간 보장이나 Codex 내부 재시도·토큰·비용의 상한이 아닙니다. 사용량 누락을 0으로 해석하지 마세요.

기본 최종 출력은 전체 전송 envelope를 반복하는 대신 간결한 결과 요약부터 표시합니다. 유효한 `proposed-change`는 전체 제안 소스/테스트와 호스트 계산 diff·해시를 제공할 뿐 적용·검사된 수정안이 아닙니다. `no-change`, `unknown`, `refused`는 구분합니다. 전송 메타데이터는 호스트가 연결한 문맥이지 모델 작성 사실의 독립 증명이 아니며 mock 응답도 실제 생성의 증거가 아닙니다.

최종 JSON의 `kind`는 `codex-generated-repair-workflow`입니다. 바깥 `status`는 흐름(`generation-ready`, `not-shared`, `preview-changed`, `generation-failed`)을 설명하고 `proposal_status`는 제안 상태를 별도로 설명합니다. `generation-ready`는 검증한 응답이지 수정 성공이 아닙니다. `generation`은 전송 envelope를, `proposal_preview`는 실행 기능이 없는 호스트 계산 미리보기를 보존합니다. `execution_status`, `patch_application`, `restoration_status`는 `not-run`이고 `applied`는 false입니다. `application_turn_attempts`는 로컬 어댑터 호출 수이지 제공자가 수락하거나 과금한 turn 수가 아닙니다.

### 결과 읽기

사람용 최종 화면은 흐름·제안 상태와 함께 적용 여부, 실행·패치·복구·승인 상태를 먼저 명시합니다. 빠진 상태는 성공이나 미실행으로 추정하지 않고 unknown으로 표시합니다. 이어서 변경 파일, 근거, 가정, 불확실성, 한계를 보여 주고 전체 제안 소스·테스트·diff를 각각 한 번씩 표시합니다. 긴 식별자·해시·중복 전송 envelope는 이 기본 화면에서만 생략하며 결과 데이터에서는 제거하지 않습니다.

생성한 텍스트와 코드는 계속 신뢰하지 않는 데이터입니다. 표시하는 각 줄에 접두사를 붙이고 ASCII 이스케이프 처리하므로 터미널 제어 문자·양방향 문자·비ASCII 텍스트가 표시 방식을 몰래 바꾸지 못합니다. 원문을 이스케이프 없이 표시하는 옵션은 없습니다.

- `--details`는 사람이 읽는 결과 뒤에 전체 최종 JSON을 추가하며 요청을 다시 보내지 않습니다.
- `--json`은 전체 최종 결과 또는 오프라인 미리보기 하나만 stdout에 내보내고 대화형 공유 미리보기·질문은 stderr에 표시합니다. `--details`를 함께 지정해도 JSON은 바뀌지 않습니다.
- 공유 동의 화면은 축약하지 않습니다. `--preview-only`를 포함한 전체 공유 미리보기 원문은 `--details`와 관계없이 그대로 유지합니다. 새 공유 확인 문구를 입력하기 전에 이를 읽어야 합니다.

이는 출력 형식 옵션일 뿐 공유 승인, 생성 코드 실행, 패치 적용, 파일 복구, 생성·수정 수용을 뜻하지 않습니다.

## 유지하는 시나리오

[시나리오 소스](../../../../src/authzest/codex/generated_repair_scenario.py)는 합성 `app.py` 하나, `GET /documents/{document_id}` 경로 하나, `alice` 또는 `bob`이 소유한 메모리 내 문서를 포함합니다. 의도적으로 누락한 소유권 검사는 데모 조건이지 실제 운영 취약점 발견이 아닙니다. `X-Demo-Actor`는 호출자가 선택하는 fixture 데이터이며 **인증이나 신뢰할 수 있는 신원이 아닙니다**.

assistant가 작성한 정책은 **유지관리자 검토 대기** 상태입니다. 소유자에게는 기존 성공 응답을 유지하고, 다른 사용자의 문서는 내용을 노출하지 않고 403으로 거부하며, 누락·미등록 actor는 401, 유효한 actor가 없는 문서를 요청하면 404로 처리하도록 제안합니다. 이는 제안한 예상값과 소스 선언이며 관찰한 HTTP 결과나 독립적으로 승인한 정답 집합이 아닙니다.

요청하는 출력은 새로 작성한 방어용 pytest 파일 `tests/test_generated_ownership.py`와 `app.py`의 전체 대체 소스입니다. 경로는 고정된 이름표이지 임의 파일시스템 대상이 아닙니다. `test_before = "absent-in-planned-copy"`는 계획한 복사본을 설명하며 실제 파일시스템 관찰이 아닙니다. 등록된 after 정답 소스나 미리 작성한 테스트를 선택지로 제공하지 않습니다.

## 요청·제안·미리보기

[계약 API](../../../../src/authzest/codex/generated_repair.py)는 변경 불가능한 요청·제안·미리보기 래퍼를 제공합니다.

- `build_generated_repair_request()`와 `validate_generated_repair_request(raw)`는 유지하는 소스·정책·선언·프롬프트·응답 스키마를 결합합니다.
- `generated_repair_prompt(request)`와 `generated_repair_output_schema(request)`는 구조화된 출력 요청을 설명하며 전송하지 않습니다.
- `validate_generated_repair_proposal(raw, request)`는 신뢰하지 않는 응답이 해당 요청에 맞는지 확인합니다.
- `prepare_generated_repair_preview(proposal, request)`는 호스트에서 소스·테스트 diff와 내용 결합값을 계산합니다. 모델이 제공한 diff를 신뢰하거나 적용하지 않습니다.

`proposed-change`만 제안을 포함합니다. 고정 `source_path`, 일치하는 `before_sha256`, 전체 `after_text`, 고정 `test_path`, 새로운 `test_text`가 필요합니다. 나머지 `no-change`, `unknown`, `refused`는 `proposal: null`이어야 하며, `unknown`과 `refused`는 불확실성 항목도 요구합니다. 제안이 있다는 사실만으로 실제 모델이 작성했음을 입증하지 않습니다.

생성 소스·테스트 각각은 파싱 전 UTF-8 16,384바이트, 파싱 전용 AST는 최대 4,096개 노드·깊이 64로 제한합니다. JSON·프롬프트·미리보기 데이터에는 256 KiB 한도를 적용합니다. 현재 계약의 결합값을 재검증하고 호스트에서 LF를 고려한 소스·테스트 diff와 해시를 계산합니다. 미리보기 상태는 미검증·미적용·실행 안 함으로 유지합니다.

객체 루트 출력 스키마는 형식 유도 후보이지 최종 검증기가 아닙니다. 호스트는 상태/제안 연결·필수 불확실성·고유 근거 ID·정확한 UTF-8 바이트 제한·AST 예산을 추가로 검사합니다. [현재 구조화 출력 스키마 안내](https://developers.openai.com/api/docs/guides/structured-outputs)를 따르는 것이 고정 App Server의 호환성을 입증하지는 않으며 실제 호환성은 미검증입니다.

## 검증이 입증하지 않는 것

- AST 파싱은 컴파일·테스트 수집·OS sandbox·의미 검증·안전성 검사가 아닙니다. 문법이 유효해도 요청한 제한이나 정책을 위반할 수 있습니다.
- ID와 해시는 내용을 결합할 뿐 검토자·모델 인증, 최신성 증명, 공유·실행·적용·복구 승인이 아닙니다.
- 모델이 작성한 테스트가 같은 모델의 수정안을 통과시키는 것만으로 올바른 수정임을 독립적으로 입증할 수 없습니다. 이번 단계에서는 생성 코드를 실행하지 않습니다.
- 과거 등록 템플릿 승인은 새 시나리오나 생성 코드를 승인하지 않습니다. 현재 산출물을 수용된 실제 trial, 검증된 수정안, 정식 릴리스 조건 완료로 표시하지 않습니다.

## 다음 경계

[#152](https://github.com/casing1/authzest/issues/152)에서 새 실행 경계와 유지관리자가 관리하는 독립적인 소유자·비소유자·익명·정상 사용 대조군부터 정의·검토해야 합니다. 별도 승인한 격리 환경의 before/after 검사는 테스트 실패와 인프라 실패를 구분해야 합니다. 복사본 전용 적용, 정확한 diff 검토, 변경된 파일에 대한 거부, 복구에도 각각 검토한 동작과 동의가 필요하며 이 문서는 이를 승인하지 않습니다.

[#153](https://github.com/casing1/authzest/issues/153)은 실제 scan·PoC/테스트·diff·검사·복구 결과를 읽기 전용 로컬 React UI에 표시할 예정입니다. 초기 실행·승인 제어는 CLI에 두며 클라우드 배포는 필요하지 않습니다. 이러한 통합은 아직 후속 작업입니다.

어댑터는 [공식 Codex App Server 문서](https://learn.chatgpt.com/docs/app-server)의 현재 turn에 `outputSchema`를 전달하는 방향을 사용합니다. 소스 연결·오프라인 스키마·mock 테스트는 변경하지 않은 Codex 고정 버전 `0.153.0`의 **실제 제공자 호환성 근거가 아니며**, 실제 요청에는 별도 동의와 수용 근거가 필요합니다.
