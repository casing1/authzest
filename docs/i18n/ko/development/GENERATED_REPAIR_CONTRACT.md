<p align="center">
  <a href="../../../development/GENERATED_REPAIR_CONTRACT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 계약과 선택형 Codex 요청

[문서 목차](../INDEX.md)

## 상태 — 2026-11-19 KST

[#151](https://github.com/casing1/authzest/issues/151)은
[과목 릴리스 범위](https://github.com/casing1/authzest/issues/150)의 오프라인 요청·제안 계약을 선택형
`codex-generate` 어댑터에 연결합니다. [과제 시연](../guides/COURSE_DEMO.md#인용할-검증-근거)은 관리 대상
사례의 `34baebc`에서 확인한 실제 응답 한 건을 기록합니다. #151에는 최종 후보 수용 검증이 남았습니다.

미리보기 경로는 관리 대상 요청을 오프라인으로 보여 줍니다. 제안 전용 명령은 모델을 명시하며 정확한
공유 승인 뒤 요청 한 건을 허용합니다. 별도의 복사·검사·적용·복구 단계는
[생성 파일 흐름 안내](../guides/GENERATED_FILE_WORKFLOW.md)를 참고하세요.

## 다음 후보에서 보관된 기록 읽기

과제 시연은 합성 FastAPI 앱에서 시작합니다. 정책상 소유자는 자신의 활성 기록과
보관된 기록을 읽을 수 있지만, 현재 기준 동작은 보관된 기록의 조회를 잘못 거절합니다. 대기 중인 기록은
계속 조회할 수 없습니다. 소유권 확인과 익명 사용자·없는 기록의 처리는 시연 앱이 담당합니다.

다음 명령으로 공유할 전체 입력을 오프라인에서 확인합니다. `EXPLICIT_MODEL`에는 사용할 모델 식별자를
넣습니다. 미리보기를 JSON으로 저장하려면 `--json`을 추가합니다.

```bash
authzest owner-read-suggest --model EXPLICIT_MODEL --preview-only
```

POSIX Python 설치판에서 `--preview-only`를 빼면 전체 요청을 확인한 뒤 기존 Codex 로그인으로 전송할지
선택할 수 있습니다. Enter를 누르면 전송을 거절합니다. 요청에는 패키지의 조회 가능 상태 규칙, 정책,
기대와 달랐던 응답이 들어갑니다. Codex가 소유자의 보관 기록 조회를 검사하는 새 테스트와 규칙 수정안을
작성하면, CLI는 응답 구조를 검증하고 두 파일의 diff를 표시합니다. 이 단계의 테스트 실행과 패치 적용은
`not-run`으로 기록합니다. `--json`에서는 대화가 표준 오류로, 최종 결과 한 건이 표준 출력으로 나옵니다.

### 비공개 복사본 준비

다음 명령으로 CLI가 지원하는 모든 플랫폼에서 로컬 복사 계획과 검사 7개의 기대 결과를 미리 볼 수 있습니다.

```bash
authzest owner-read-suggest --model EXPLICIT_MODEL --prepare-copy --preview-only
```

지원되는 POSIX 소스 설치판에서 `--preview-only`를 빼면 수정안을 요청하고 로컬 복사 계획을 검토할 수
있습니다. 자료 공유와 디렉터리 생성은 각각 승인합니다. 현재 명령에서 검증된 수정안이 있을 때만 복사
확인이 표시됩니다. 계획에는 설치판의 기준 바이트, 이번 요청과 공유 결정, 소스와 테스트의 정확한 diff 및
SHA-256 해시가 연결됩니다. 설치된 파일의 해시만으로 Git 커밋을 식별할 수는 없습니다. 매번 새로운 난수를 복사 확인 문구에
연결하며, 300초 이내에 한 번만 승인할 수 있습니다. 거절하거나 기한이 지나면 복사 단계를 종료합니다.
파일시스템 작업의 완료 시간에는 고정 상한이 없습니다.

CLI는 시스템 `/tmp` 아래에 새 비공개 디렉터리(0700)를 만듭니다. macOS에서는 이 경로의 별칭을 해석하며
작업 디렉터리와 `TMPDIR` 설정을 사용하지 않습니다. 이름이 이미 있는 파일과 심볼릭 링크를
거부하며 새 파일(0600)의 식별 정보와 바이트를 검증합니다. diff의 경로는 패키지 소스와 제안된 테스트를
가리킵니다. 복사본에는 최대 세 파일을 담으며, 검증된 ASCII 본문은 파일당 최대 4 KiB, 합계 최대 12 KiB입니다.

| 파일                          | 준비 시점의 내용                        |
| ----------------------------- | --------------------------------------- |
| `availability.py`             | 설치판의 기준 규칙 원문                 |
| `test_owner_archived_read.py` | 검토용으로 보관한 생성 회귀 테스트 원문 |
| `proposed-availability.txt`   | 텍스트로 보관한 규칙 수정안             |

로컬 단계는 CLI 프로세스 안에서 파일을 준비합니다. worker 기동, 제공자 자격증명 조회, HTTP 요청과 생성
파일 실행은 수행하지 않으며 worker 출력도 없습니다. 원본 체크아웃은 유지됩니다. 생성 중 실패하면 보고된 디렉터리와 파일 상태를
확인하세요. CLI는 부분 복사본을 보존하며 다시 열기·덮어쓰기·재시도 기능을 제공하지 않습니다. `--json`으로
실행하면 최종 CLI 결과에 복사 상태가 기록됩니다. 복사본에는 위 세 파일만 들어갑니다. 파일 권한의
보호 범위는 사용자 계정 단위이므로 같은 사용자 권한의 다른 프로세스는 파일을 바꿀 수 있습니다.

### 설치 후보에서 남은 검증

worker를 활성화하기 전에 실행 설계 검토가 필요합니다. 설계에는 프로세스 기동과 격리, 네트워크와 자격증명
접근, 시간·출력·자원 한도, 정리 및 실패 기록 방법을 명시해야 합니다. 수정 전 검사, diff 수용, 적용, 수정
후 검사와 복구는 각각 현재 바이트와 선행 결과를 확인하고 별도로 결정합니다.

정식 시연에서는 생성된 소유자 조회 테스트를 실행하고 그 결과를 관리자가 정한 독립 검사 7개의 결과와 따로
기록합니다. 소유자의 보관 기록 조회는 403에서 기대 본문을 담은 200으로 바뀌어야 합니다. 나머지 여섯 건은
소유자의 활성 기록 조회 200, 다른 사용자의 활성·보관 기록 조회 각각 403, 익명 사용자의 활성 기록 조회 401,
소유자의 없는 기록 조회 404, 소유자의 대기 기록 조회 403입니다. 복구 때는 기준 규칙의 원래 바이트와 보관한
테스트 파일의 상태를 확인합니다. 사용자가 파일을 편집했다면 편집을 보존하고 미복구 상태를 보고합니다.
복사본 준비만으로는 수정 전 검사·수정 후 검사·복구 결과가 생기지 않습니다.

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

객체 루트 출력 스키마는 형식 유도 후보이지 최종 검증기가 아닙니다. 호스트는 상태/제안 연결·필수 불확실성·고유 근거 ID·정확한 UTF-8 바이트 제한·AST 예산을 추가로 검사합니다. [구조화 출력 스키마 안내](https://developers.openai.com/api/docs/guides/structured-outputs)를 참고하세요. 후보의 호환성은 고정 App Server의 실제 응답으로 확인해야 합니다.

## 검증이 입증하지 않는 것

- AST 파싱은 컴파일·테스트 수집·OS sandbox·의미 검증·안전성 검사가 아닙니다. 문법이 유효해도 요청한 제한이나 정책을 위반할 수 있습니다.
- ID와 해시는 내용을 결합할 뿐 검토자·모델 인증, 최신성 증명, 공유·실행·적용·복구 승인이 아닙니다.
- 모델이 작성한 테스트가 같은 모델의 수정안을 통과시키는 것만으로 올바른 수정임을 독립적으로 입증할 수 없습니다. 이번 단계에서는 생성 코드를 실행하지 않습니다.
- 과거 등록 템플릿 승인은 새 시나리오나 생성 코드를 승인하지 않습니다. 현재 산출물을 수용된 실제 trial, 검증된 수정안, 정식 릴리스 조건 완료로 표시하지 않습니다.

## 검증과 결과 표시

[#152](https://github.com/casing1/authzest/issues/152)는
[생성 파일 흐름](../guides/GENERATED_FILE_WORKFLOW.md)의 후보 수용을 추적합니다.
[오프라인 검증 기반](GENERATED_REPAIR_VERIFICATION.md)은 관리하는 대조 기준을 정의하고 공급된 관찰을
평가합니다. 활성 흐름은 그 대조를 별도 결정 단계와 연결하고 테스트·인프라·복구 결과를 기록합니다.

[#153](https://github.com/casing1/authzest/issues/153)의 [로컬 뷰어](../guides/RESULT_VIEWER.md)는
최종 JSON을 읽기 전용으로 표시합니다. 공유와 실행 단계 결정은 CLI에서 처리합니다. 어댑터는
[Codex App Server 문서](https://learn.chatgpt.com/docs/app-server)에서 설명하는 현재 turn의
`outputSchema` 필드를 사용합니다.
