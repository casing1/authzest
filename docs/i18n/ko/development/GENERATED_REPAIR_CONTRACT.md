<p align="center">
  <a href="../../../development/GENERATED_REPAIR_CONTRACT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 생성 수정 계약

[문서 목차](../INDEX.md)

## 상태 — 2026-11-09 KST

이 문서는 [과목 릴리스 범위](https://github.com/casing1/authzest/issues/150)에 포함된 [#151](https://github.com/casing1/authzest/issues/151)의 첫 오프라인 계약 단계입니다. 메모리 안에서 요청과 신뢰하지 않는 제안을 준비·검증하며, 실제 AI 생성·생성 테스트 실행·파일 적용·결과 UI를 **제공하지 않습니다**. #151은 열린 상태입니다. 기존 등록 템플릿의 수용 결과는 새로 작성한 수정안의 수용 결과가 아닙니다.

이 계약은 Codex 시작, 자격 증명이나 임의 저장소 읽기, 복사본 생성, 파일 쓰기, 테스트 실행, 실행 동의 부여를 하지 않습니다. 기존 제품·리포트 버전과 Codex 고정 버전·모델 설정도 바뀌지 않습니다.

## 오프라인 입력 미리보기

이 변경을 포함한 소스 체크아웃을 설치한 환경에서 다음 명령은 고정 요청을 전송하지 않고 표시합니다.

```bash
authzest generation-preview
authzest generation-preview --json
```

기본 출력은 생성하지 않는다는 안내와 함께 전체 프롬프트·응답 스키마를 표시합니다. JSON 모드는 `status: "preview-only"`, `model_invoked: false`, `applied: false`, `execution_status: "not-run"`인 `generated-repair-request-preview` 문서 하나를 출력합니다. 모델·저장소 경로·실행 옵션은 없습니다. 이는 입력 미리보기이지 생성된 제안이나 실제 생성 흐름이 아닙니다.

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

[공식 Codex App Server 문서](https://learn.chatgpt.com/docs/app-server)는 `outputSchema` 같은 구조화된 출력을 위한 향후 연동 참고 자료입니다. 이 링크와 오프라인 스키마는 기존 Codex 고정 버전 `0.153.0`의 **호환성 근거가 아니며**, 실제 연동에는 별도 검사와 동의가 필요합니다.
