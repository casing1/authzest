<p align="center">
  <a href="../../../reference/PROPOSAL_CONTRACT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 제안·결정 계약

[문서 목차](../INDEX.md) · [AI 입력/검토 계약](AI_CONTRACT.md)

## 구현 범위

#46은 #33 다음에 진행하는 #35의 첫 오프라인 단계입니다. 제안·결정 스키마는 `1.0`이며
리포트 스키마 `1.2`, 패키지 버전 `0.1.0a2`와 별개입니다. 소스 checkout의 이 모듈은 alpha.2
바이너리에 포함되지 않습니다. 새 제품 CLI/API 명령이나 스캔 동작 변경은 없습니다.

라이브러리는 호출자가 명시적으로 작성한 변경 텍스트를 제안으로 묶고 제안/결정을 검증합니다.
Codex 호출, 코드 생성, 초안 workspace 기록, 패치 적용, 테스트 실행이나 파일 복구는 하지 않습니다.
이후 별도로 승인할 연동 단계가 남아 있으므로 #35는 계속 열어둡니다.

별도 [#48 fixture 복사 서비스](../guides/FIXTURE_APPLICATION.md)는 새 POSIX 복사본에 한정해
실제 승인 적용/복구를 시연합니다. 이 계약 모듈은 계속 순수 함수이며 어느 쪽도 임의 checkout 수정·
실제 AI·검증 실행을 제공하지 않습니다.
별도의 [#50 Codex fixture 명령](../guides/CODEX_FIXTURE.md)은 엄격히 검증한 모델 초안을 이 호스트
계약에 전달합니다. 한 소유 fixture의 실제 초안·적용·복구 확인 1회가 성공했으며 승인 문구는 사용자
허가 아래 assistant가 입력했습니다. 독립적인 사람 검토는 아닙니다. 이 순수 함수를 제공자 client나 검증 실행기로 바꾸지 않으며
일반 저장소 패치 흐름도 아닙니다.
이 명령에 후속으로 추가한 #52 고정 소스 검사는 계획을 별도 승인하는 실행기입니다. 적용된 fixture의
해시를 고정하고 AST 설정만 확인하며 런타임 동작을 검사하거나 이 순수 계약의 `not-run` 결과를 바꾸지 않습니다.

## 제안 내용과 미리보기

`prepare_proposal`은 #33 요청, 검증된 검토 결과, 선택한 기존 파일의 변경 내용,
이유·명시적 불확실성·부작용·검사 식별값·예상 결과를 받습니다. `validate_proposal`은 입력/검토를
다시 검증하며 스키마/요청/검토 식별 불일치, 소스 인용 누락, 잘못된/추가 필드, 중복 대상과
변경 없는 교체를 거부합니다.

- 각 변경에는 상대 경로, 원본 UTF-8 SHA-256, 정확한 변경 텍스트와 근거 ID가 있습니다.
  해당 파일의 소스 인용이 필수입니다. ID가 존재한다고 의미상 주장을 뒷받침하는 것은 아닙니다.
- 이번 단계에서는 이미 선택한 Python 파일 최대 8개를 바꾸는 제안만 허용하며 각 텍스트는 비어 있지
  않은 최대 32,768자입니다. 경로는 ASCII 영문/숫자·밑줄·점·하이픈·구분자를 사용합니다.
  절대/상위 이동/모호한 경로, 숨김 요소, 예약 폴더와 대소문자가 충돌하는 선택 경로는 거부합니다.
  새 파일·삭제·이름 변경·권한·바이너리·Python 외 파일은 지원하지 않습니다. AI 계약의 JSON 제한도 적용합니다.
- `proposal_id`는 요청, 검증된 검토, 원본 해시, 변경 내용, 이유, 불확실성, 부작용, 검증 계획 전체에
  연결됩니다. diff가 같아 보여도 이 중 하나가 바뀌면 새로운 결정이 필요합니다.
- `proposal_preview`는 연결된 스냅샷/변경 내용으로 unified diff를 만들며 제공자가 따로 주는 diff 필드는
  거부합니다. UTF-8 내용 해시는 줄바꿈을 정규화하지 않습니다. diff는 LF 기준 줄을 세고 CRLF 데이터를
  보존하며 마지막 줄바꿈 누락을 표시합니다. 정확한 전후 해시·이유·계획을 반환합니다.
  클라이언트는 비신뢰 텍스트를 안전하게 표시해야 합니다.

검사는 비실행 식별값 `fixture-static-inventory`, `fixture-regression-tests`입니다.
향후 검증 의도이며 이미 존재하는 실행기나 실행을 허가하는 명령 목록이 아닙니다. 계약은 shell 명령,
실행 파일, 인수, 환경, 설치 hook 필드를 받지 않습니다. 예상 결과와 설명도 비신뢰 데이터입니다.
후속 구현에서는 검토한 고정 구현으로 검사를 연결하고 별도의 실행 승인을 받아야 합니다.

## 결정과 현재 상태 확인

`record_decision`은 호출자의 명시적 `approve`, `decline`, `cancel` 결정을 정확한 제안 ID와
`patch-application` 목적에 기록합니다. 사람의 신원을 인증하거나 모델 텍스트에서 동의를 추정하지
않습니다. 호출자는 동일한 시계의 유한한 시간을 제공하며 만료는 기본 300초, 양수이며 최대 1시간입니다.

`assess_decision`은 산출물을 재검증하고 결정과 현재 제안, 시간, 선택한 모든 소스 텍스트(수정 파일만이 아님),
요청에 있었다면 소스 revision을 대조합니다. 추가로 들어온 미선택 내용은 무시하며 바꾸지 않습니다.

| 사유                     | 적용 가능 | 의미                                |
| ------------------------ | --------- | ----------------------------------- |
| `pending`                | false     | 명시적인 결정 없음                  |
| `declined` / `cancelled` | false     | 명시적인 거절/취소                  |
| `stale-proposal`         | false     | 다른 제안을 가리키는 결정           |
| `clock-before-decision`  | false     | 현재 시간이 결정 이전               |
| `expired`                | false     | 현재 시간이 만료에 도달하거나 초과  |
| `stale-source`           | false     | 선택 텍스트/revision 변경 또는 누락 |
| `approved`               | true      | 제공된 상태가 오프라인 검사를 만족  |

잘못된 스키마/입력은 적용 가능 결과 대신 `ContractError`를 발생시킵니다. 모든 결과는 여전히
`applied: false`, `verification_status: not-run`입니다. 적용 가능은 검증된 수정이 아니며
소스 공유나 검증 실행을 허가하지 않습니다.

이는 내부 계약이며 **서명된 일회용·재사용 방지 권한 시스템이 아닙니다**. 같은 입력으로 두 번 검사하면
같은 결과가 나옵니다. 후속 적용 서비스는 가장 최근의 철회되지 않은 결정을 사용/소비하고,
링크를 따라가지 않고 실제 일반 파일을 읽어 루트/내용을 재확인하며 파일 경쟁을 원자적으로 처리하고
사용자 편집을 보존하며 충돌을 거부해야 합니다. 제공된 스냅샷과 경로 문자열 검사는 symlink 안전성이나
현재 디스크/Git 상태를 보장하지 않습니다. 이 검사기를 제한 없는 패치/shell 실행기에 바로 연결하지 마세요.

## 소유한 오프라인 데모

editable 개발 환경 설치 후 저장소 루트에서 실행합니다.

```bash
python scripts/demo_proposal.py
python scripts/demo_proposal.py --decision approve
python scripts/demo_proposal.py --decision cancel
python scripts/demo_proposal.py --decision approve --scenario stale-source
python scripts/demo_proposal.py --decision approve --scenario expired
python -m pytest tests/test_proposal_contract.py tests/test_proposal_approval.py
```

데모의 기본 결정은 거절입니다. `tests/fixtures/proposal_demo/main.py`만 읽고 import 없이 목록화한 뒤
호출자가 고정 작성한 `debug=True` → `debug=False` 설정 초안을 제안으로 묶습니다. AI가 발견한 취약점,
인가 테스트나 런타임 보안 보장이 아닙니다. 고정 검토 응답, 모의 결정과 상대적인 예제 시간을 사용하며
승인 시나리오에서도 fixture는 바뀌지 않고 테스트는 실행하지 않습니다. JSON은 터미널에 안전하게
표시하기 위해 제어/비ASCII 문자를 이스케이프합니다.

정확한/다중 파일 diff, 줄바꿈, 소스/검토/계획 변경, 위험 대상, 거절, 취소, 만료, 소스 누락, 잘못된
기록과 명시적인 네트워크/쓰기 금지를 테스트합니다. fixture 적용·제공자 단계는 별도 범위 안내를
참고하세요. 완전한 제공자·런타임 검증 실패·복구 완료 기준은 후속 #35의 범위입니다.
