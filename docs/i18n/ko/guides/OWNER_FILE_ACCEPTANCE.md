<p align="center">
  <a href="../../../guides/OWNER_FILE_ACCEPTANCE.md">English</a> ·
  <strong>한국어</strong>
</p>

# 설치형 소유 파일 CLI 수용 검증

[문서 목차](../INDEX.md) · [CLI 흐름](OWNER_FILE_WORKFLOW.md) ·
[파일 세션 계약](../reference/OWNER_POLICY_FILE_REPAIR.md) ·
[개발 계획](../development/DEVELOPMENT_PLAN.md)

이 문서는 **제한된 관찰 기록을 포함한 수용 검증 절차이지 실행 허가나 #82/릴리스의 모든 조건 완료가 아닙니다.**
기존 CLI와 단계별 독립 결정을 유지합니다. 무인 승인·재개/가져오기·만료 연장·worker 선택이나
새 실행 경로를 추가하지 않습니다.

## 기록된 경계 — 2026-10-30 KST

[PR #120](https://github.com/casing1/authzest/pull/120)은 필수 검사와 별도 승인한 리뷰·병합 후 main
`a0ae8792ce4c2d88d0cbbf6bc66fc13635094be2`에 소스 CLI를 전달했습니다.
그 이후의 다음 로컬 관찰은 구현 전달과 구분합니다.

- macOS/Python 3.12.7의 독립 non-editable wheel 설치에서 패키지 파일 64개가 선택한 소스와
  일치했습니다. 기존 설치 smoke 13개와 추가 오프라인 흐름 검사 10개를 통과했습니다.
  유지하는 smoke script가 23개로 변경됐거나 pipx·업그레이드·native/플랫폼 수용을 마쳤다는 뜻은 아닙니다.
- 별도로 승인한 추천 시도 2회는 기존 ChatGPT 로그인, Codex 0.153.0, adapter 0.1, 정확한 모델
  `gpt-6-astra`, candidate `before`와 같은 고정 공개 자료를 사용했습니다.
  각각 host 검증을 통과한 `registered-change`를 받았으며 임의 교체 코드를 생성하지 않았습니다.

| 시도    | 측정한 추천 응답                    | 관찰한 중단 지점                                                                                      |
| ------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 첫 번째 | 29.831초; 입력 7,750 / 출력 715토큰 | 확인 시 copy 유효 시간이 지나 Enter로 복사를 거절했습니다. 종료 0, 복사본·worker 없음.                |
| 두 번째 | 24.860초; 입력 7,750 / 출력 703토큰 | 비공개 복사본 하나와 전체 before 계획을 준비·검증한 뒤 before 실행을 의도적으로 거절했습니다. 종료 0. |

두 번째 실행은 `policy.py`·`before.txt`·`after.txt`·`record.json`을 보존했습니다.
디렉터리 0700, 일반 단일 링크 파일 0600을 확인했습니다. 전체 application·plan·recipe 연결,
정확한 소스 바이트와 정수 파일 식별자를 대조했습니다. 최종 상태는 `ready-before`,
generation 1이며 worker dispatch·diff 수용·적용·after 검사·복구는 없었습니다.
두 시도 모두 경고 1개와 재시도 알림 0개를 보고했지만 제공자 내부 재시도나 비용의 강제 상한을
뜻하지 않습니다. 모델 식별은 협상된 thread metadata이지 독립적인 served-model 증명이 아닙니다.
일회 승인은 모두 소비됐으며 닫힌 복사본은 재개할 수 없습니다.

첫 번째 최종 stdout JSON은 파싱에 성공했습니다. 두 번째는 도구 출력 수집 한도로 최종 stdout
일부가 잘려 **전체 최종 JSON의 파싱을 확인하지 못했습니다.**
전체 before 미리보기·완전한 최종 workflow 하위 객체·영속 기록·실제 보존 파일은 별도로 대조했습니다.
이를 조립해 손실된 stdout 원본을 보존했다고 표시하면 안 됩니다. 상세 로컬 기록과 식별자는 비공개로
유지합니다. 이는 기록된 관리자 walkthrough이지 독립 benchmark나 인증된 receipt가 아닙니다.

이 두 시도는 설치형 정책 실행이나 수정·복구를 입증하지 않았습니다. 아래의 이후 별도 승인한
정상 경로는 그 제한된 근거를 추가하며 이전 수집 공백을 소급 보완하지 않습니다.
#82/#81/#35와 별도 #83 릴리스 gate는 미완료입니다. 공개 alpha.3·패키지 `0.1.0a3`·
리포트 스키마 `1.2`는 그대로입니다.

## 설치형 정상 경로 관찰 — 2026-10-30 KST

main `c868152590b70fdaae6fd8274d5344b09e5d948f`의 새 non-editable wheel 설치에서 패키지
파일 64개가 소스와 일치했고 기존 설치 smoke 13개와 추가 오프라인 흐름 검사 10개를 통과했습니다.
이후 별도 승인한 설치형 CLI walkthrough 한 번을 macOS/Python 3.12.7, Codex 0.153.0,
adapter 0.1, 정확한 모델 `gpt-6-astra`, candidate `before`로 완료했습니다.
제품은 개발 전용 실행 helper 없이 설치된 console entrypoint에서 동작했으며 별도 읽기 전용
도구로 보존 증거를 대조했습니다. 소스 설치 host 한 대의 근거입니다.

- 현재 추천은 host 검증을 통과해 기존 등록 템플릿을 선택했습니다. 고정 공개 합성 쌍·기준/가정·
  검토한 사례 8개·prompt/schema만 공유했으며 임의 교체 소스나 새 사례를 생성하지 않았습니다.
- 공유/복사/before/diff/apply/after/restore의 현재 미리보기 일곱 개를 각각 검토하고 해당하는
  원래 유효 시간 안에 새 정확한 선택을 입력했습니다. 승인 자동화·결정 가져오기·모델 대체·
  AuthZest 수준 재시도·만료 상태의 이어 실행은 사용하지 않았습니다.
- 새 비공개 복사본 하나를 수정 전에 검사해 예상값 6/8개와 일치했고 `non-owner`와
  `exact-owner-no-normalization`의 의도한 과도 허용을 관찰했습니다. 정확한 등록 diff를 수용해
  복사본에만 적용했으며 캡처한 실제 적용 바이트의 검사에서 예상값 8/8개와 일치했습니다.
- 고정 worker 검사 두 건은 각각 한 번씩 종료 `0`, 자식/작업 공간 정리 확인으로 끝났습니다.
  별도 복구를 완료했고 실제 보존 파일이 정확한 등록 before 바이트와 일치했습니다.
  최종 `restored-before`, generation 3이며 파일/증거 연결을 확인했습니다.
- 원본 stdout 전체가 최종 JSON 하나로 파싱됐고 원본 stderr·종료 코드·비공개 파일/기록을
  보존했습니다. CLI와 수집 모두 종료 `0`입니다. 디렉터리 0700, 일반 단일 링크 파일 0600을
  검증했습니다. 최종 닫힌 checkpoint와 영속 기록은 `closed` 외에는 일치하고 원본 checkout은
  clean을 유지했습니다. 원본 증거·식별자·계정 정보·사용량은 비공개로 둡니다.

추천 한 번과 복사본/단계별 허용 횟수는 모두 소비됐습니다. 협상 모델 metadata는 독립적인
served-model 증명이 아니며 내부 전송 재시도/사용량을 강제 제한하지 못합니다. 과거 after 통과는
적용 바이트의 결과이지 현재 복구된 before 파일의 통과가 아닙니다. 독립 benchmark·인증된 승인·
HTTP/인증/DB 검사·설치형 실제 고장 주입·pipx/업그레이드/native 수용·릴리스 결정이 아닙니다.
기존 오프라인 거절/사용자 편집/복구 검사와 최종 #82 검토는 별개이며 상위 이슈를 종료하지 않습니다.

## #82 근거 매핑과 남은 검토

| 기준                                           | 기록한 근거                                                                                                                                                                                      | 남은 경계                                                                                              |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| 설치형 활성 정상 경로                          | 위의 `c868152` 관찰: 현재 추천·복사본 하나·실제 before/적용 after 검사·복구, 원본 JSON 전체·비공개 파일/기록 대조                                                                                | macOS/Python 소스 설치 한 건이며 임의 저장소·native/업그레이드 수용 아님                               |
| 거절/실패/사용자 편집/복구와 no-change/unknown | 기존 guarded [조율 테스트](../../../../tests/test_codex_owner_file_workflow.py)와 [CLI 테스트](../../../../tests/test_codex_owner_file_cli.py), 가짜 adapter/scripted 관찰·pytest 소유 파일 사용 | 실제 고장 주입이 아닌 오프라인 통합 근거; 테스트 매핑만을 위해 제공자/worker 재실행이 필요한 것은 아님 |
| 사람용/JSON 출력과 재현 안내                   | [CLI 안내](OWNER_FILE_WORKFLOW.md), 전체 동의 미리보기·분리된 출력 스트림·수집한 설치형 정상 경로                                                                                                | 관리자의 최종 재현/한계 검토는 미완료; JSON 실행 한 번으로 모든 사람용 렌더링 분기를 관찰하지는 않음   |
| 새로운 제한 결정과 증거 보존                   | 현재 선택 일곱 개를 각각 검토, 정확한 application/plan/파일 연결·복구 바이트·비공개 기록 대조                                                                                                    | 일회 허용은 소비됐고 선택/기록은 비인증, authorization `unknown`; 재사용·독립 보안 증명 아님           |
| 전달과 상위 종료                               | PR #120 구현과 PR #121 runbook은 각각 정확한 head 검사/리뷰 완료                                                                                                                                 | 이번 문서 갱신의 자체 head CI/리뷰·정상 병합이 필요하며 #81/#35를 대조한 뒤 종료를 별도로 판단         |

이 매핑은 근거의 출처를 기록할 뿐 모든 기준의 수용 완료·추가 실제 실행 요청·릴리스 조건 면제나
이슈 종료 권한을 뜻하지 않습니다.

## 새 활성 실행 전

- 정확히 선택한 소스 commit/tree, non-editable 설치·module 위치, Python·의존성 버전과
  절대 console entrypoint를 확인합니다. 버전 출력만으로 같은 버전의 미출시 소스와 PATH의
  오래된 바이너리를 구분할 수 없습니다.
- 지원되는 POSIX non-frozen 소스 경로를 사용합니다. 원본 checkout을 깨끗하게 유지하고
  임의 저장소 경로·목적지·소스·worker나 가져온 receipt를 추가하지 않습니다.
- 계정·정확한 모델·전체 고정 공유 자료·최대 application 시도·timeout을 새로 범위를 정해 승인받습니다.
  정리 대기가 추가되며 제공자 내부 재시도·토큰·비용을 독립적으로 강제 제한하지 못함을 명시합니다.
  모델 대체나 자동 두 번째 시도는 없습니다.
- 시작 **전에** 검토 가능한 시간을 확보합니다. 각 효과에는 여전히 전체 계획과 현재의 정확한 선택이
  필요합니다. 계획 준비 허가는 실행 동의가 아닙니다.
- 이전 추천·복사본·결정으로 CLI를 재시작할 수 없습니다. 새 호출은 새 공유 선택 이후 새 추천을
  시도합니다. 손실된 로그만 보충하려고 다시 호출하지 않습니다.
- no-change/unknown은 복사본 없는 유효한 결과이며 수정을 강요하지 않습니다.

## 공유 전에 원본 출력 보존

선택적으로 다음 수집 방식을 사용하려면 새 Bash 터미널을 엽니다. 세 placeholder를 승인한 설치본과
정확한 모델로 바꾸며 CLI/Python 경로는 같은 소스 환경이어야 합니다. shell의 수집 설정이지 새 제품
옵션이 아닙니다. **아래 활성 명령은 계정 사용량을 소비할 수 있으며 위의 새 승인 없이 실행하면 안 됩니다.**

질문을 계속 화면에 표시하면서 stderr와 최종 stdout JSON 하나를 따로 저장합니다.
`--preview-only`를 활성 흐름의 근거로 사용하거나 답변을 pipe로 보내거나 승인 문구를 자동화하거나
예전 challenge를 복사하지 않습니다. shell `errexit`를 켜지 말고 CLI 실패 코드도 기록합니다.
리다이렉션 순서는 의도적입니다. stderr는 pipe에, stdout은 JSON 파일에 직접 보냅니다.
다른 명령이 덮어쓰기 전에 Bash의 `PIPESTATUS` 두 값을 즉시 저장합니다.

```bash
authzest_cli="/absolute/path/to/source-venv/bin/authzest"
authzest_python="/absolute/path/to/source-venv/bin/python"
authzest_model="YOUR_EXACT_MODEL_ID"
umask 077
authzest_evidence=$(mktemp -d "${TMPDIR:-/tmp}/authzest-cli-acceptance.XXXXXX") || exit 1
: > "$authzest_evidence/result.json" || exit 1
: > "$authzest_evidence/interaction.log" || exit 1
"$authzest_cli" codex-owner-repair --model "$authzest_model" --candidate before --timeout-seconds 120 --file-workflow --json 2>&1 > "$authzest_evidence/result.json" | tee "$authzest_evidence/interaction.log" >&2
authzest_pipe_status=("${PIPESTATUS[@]}")
authzest_cli_exit=${authzest_pipe_status[0]}
authzest_capture_exit=${authzest_pipe_status[1]}
printf '%s\n' "$authzest_cli_exit" > "$authzest_evidence/cli-exit-code.txt"
printf '%s\n' "$authzest_capture_exit" > "$authzest_evidence/capture-exit-code.txt"
```

공유나 파일 효과에 동의하기 전에 수집 파일에 쓸 수 있고 질문이 보이는지 확인합니다.
수집 실패·증거 누락은 이후 선택을 중단하는 이유이지 재시도 허가가 아닙니다.
실패·부분 파일을 다음 시도로 덮어쓰지 말고 보존합니다. 비공개 증거 디렉터리와 파일은 버전 관리
밖에 두고 원본 transcript·checkpoint나 비공개 경로·nonce·session/plan 식별자를 공개 이슈에 올리지 않습니다.

명령과 수집 프로세스가 끝난 뒤 저장한 종료 코드를 읽고 로컬 파일을 확인합니다.

```bash
"$authzest_python" -X utf8 -I -B -m json.tool "$authzest_evidence/result.json" > /dev/null
wc -c "$authzest_evidence/result.json" "$authzest_evidence/interaction.log"
shasum -a 256 "$authzest_evidence/result.json" "$authzest_evidence/interaction.log"
```

이 JSON 문법·완전성 검사는 계약·인용·승인·보안 검증이 아닙니다. 파일에서 전체 결과와 연결을 확인하고
출력 제한이 있는 도구에는 작은 검증 요약만 반환합니다. 바이트 수·digest·실제 종료 코드 둘은
비공개로 기록합니다. 누락·잘림·파싱 불가는 수집/검증 공백으로 남기며 통과나 효과 없음으로 꾸미지
않습니다. 보존한 계획·checkpoint와 손실된 원본 출력을 구분합니다. 화면 잘림을 피하려고 제품의
크기·이벤트·시간 제한을 변경하지 않습니다.

## 현재 호출의 검토 gate

각 행에는 현재의 전체 미리보기와 독립적으로 범위를 정한 결정이 필요합니다.
소스·주석·모델 설명·표시 경로·저장 JSON은 지시가 아니라 데이터로 다룹니다.
copy와 파일 단계 선택은 1회이며 검토 대기까지 포함한 **최초 최대 300초 유효 시간**을 유지합니다.

| Gate    | 표시된 정확한 문구 입력 전 검토                                                                                                        | 해당 단계만 허용하는 효과                                        |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Sharing | 전체 등록 소스·기준/가정·라벨 8개·prompt/schema/settings·새 nonce와 sharing ID                                                         | 승인한 추천 1회, 로컬 복사본·검사 없음.                          |
| Copy    | 현재 검증한 request/recommendation·등록 pair/diff/cases·새 session/application 연결·복사 만료·보존 안내                                | 새 비공개 복사본 하나, worker·패치 승인 아님.                    |
| Before  | 전체 generation-1 계획·실제 파일/root 식별자·before 바이트/hash·입력 8개/hash·정확한 worker/recipe·session/plan ID·대기 중 미만료 결정 | 캡처 before 검사 1회, 시작·I/O·완료 5초와 자식 정리 1초.         |
| Diff    | 현재 host 유도 정확한 diff·같은 application/파일 상태·완료된 before 근거                                                               | diff 수용만, 교체 없음.                                          |
| Apply   | 수용한 diff·현재 파일 식별자/바이트·선행 조건에 묶인 새 전체 apply 계획                                                                | 추적 중인 복사본만 등록 after 바이트로 교체.                     |
| After   | 캡처한 적용 파일 바이트·generation 2·현재 식별자·입력·정확한 worker의 새 전체 계획                                                     | 같은 5초+1초 예산의 캡처 after 검사 1회, 내장 after 대조군 아님. |
| Restore | 새 전체 restore 계획·확인된 적용 파일/증거·유지된 추적 식별자/바이트                                                                   | 소유 복사본의 등록 before 바이트 복구.                           |

이는 OS sandbox나 모든 파일시스템 작업의 강제 시간 상한이 아닙니다.
거절·취소·만료는 미승인 후속 효과를 중단하며 계획 표시는 만료를 갱신하지 않습니다.
늦은 결정은 정상 거절 대신 검증 실패가 될 수 있습니다. 계속하려고 계획을 다시 열거나 대체하거나
연장하지 않습니다. EOF·인터럽트는 이후 복구 질문에 대한 답변이 아닙니다.

after 검사가 실패하거나 거절돼도 적용 복사본이 확인된 상태라면 복구에는 새 별도 승인 계획이
필요합니다. 사용자 편집·누락 증거·불확실한 쓰기는 안전한 진행/복구를 막고 상태를 unknown으로
남길 수 있습니다. 정리 실패는 검사 성공 판정을 막으며 별도 점검이 필요합니다. 복구 가능 여부는
확인된 적용 파일·증거와 새로운 결정에 따릅니다. 종료 0이 검증된 수정이거나 0이 아니면 파일 변경이 없다고 가정하지 않습니다.
복사본을 보존하고 확인된 증거를 검토합니다. 이 문서는 자동 rollback·삭제·수동 덮어쓰기·제공자
재시도를 승인하지 않습니다.

## 완료 판정과 남은 gate

모든 단계를 승인한 등록 정상 경로는 before 실관찰 6/8 일치
(의도한 non-owner·exact-owner-no-normalization 과도 허용), 적용 after 실관찰 8/8,
확인된 정확한 diff·적용·복구, 최종 `restored-before` / generation 3, 일관된 파일 연결,
프로세스 완료/정리와 보존 증거가 필요합니다. 이 수치는 **새 실행의 기준이지 실행 허가나 미래 실행의
관찰이 아닙니다.** 위의 제한된 기록은 정상 경로 한 건의 완료를 나타냅니다.
인가 상태는 `unknown`이며 HTTP·인증 제공자·DB·endpoint 강제는 검사하지 않습니다.

상위 제공자 시도·설정·식별·사용량·지연과 제공자 호출 수 0인 순수 미리보기를 구분합니다.
실행 완료와 비교 통과를 구분합니다. 과거 after 통과는 이전 적용 바이트의 결과이지 복구한 before
파일의 통과가 아닙니다. 부분 효과·거절·unknown을 모두 확인하고 `completed`를 강요하지 않습니다.
close는 파일 삭제나 영속 기록 재작성 없이 descriptor를 해제하므로 최종 메모리의 `closed=true`와
마지막 영속 `closed=false`가 다를 수 있습니다.

기존 임시 파일·가짜 adapter·scripted worker 테스트는 거절·실패·사용자 편집·복구 충돌을
오프라인으로 검사했으며 설치형 실제 고장 주입 관찰이 아닙니다.
이 검사, 실제 설치형 정상 경로 또는 타당한 변경 없음, 관리자가 검토한 재현 가능한 walkthrough,
필수 최신 head CI·리뷰를 별도 #82 근거로 유지합니다. 소스 API 관찰·이 절차서·잘린 수집 결과나
통과한 mock으로 상위 흐름을 닫거나 릴리스를 발행하지 않습니다.
