<p align="center">
  <a href="../../../guides/FIXTURE_DEMO.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 fixture 단계별 시연

[문서 목차](../INDEX.md) · [복사본 적용 경계](FIXTURE_APPLICATION.md)

## 범위와 제공 상태

[#65](https://github.com/casing1/authzest/issues/65)는 alpha.3 이후 `authzest fixture-demo`를 추가합니다.
이 변경을 포함한 소스 revision을 설치하세요. 공개 alpha.3 바이너리에는 이 명령이 없습니다.
패키지에 포함한 관리 대상 fixture와 호출자가 작성한 mock 검토·제안을 사용합니다.
저장소의 `scripts/`·`tests/` 디렉터리나 Codex 설치·계정·네트워크 연결이 필요하지 않습니다.
실제 AI 결과나 새 릴리스가 아닙니다.

제안하는 유일한 변경은 새 비공개 fixture 복사본의 고정된 `debug=True` → `debug=False` 교체입니다.
기존 checkout이나 원본 fixture 파일은 수정하지 않습니다. 처음에는 지원하는 POSIX 파일 연산이
필요하며 Windows 등 미지원 시스템에서는 파일 생성 전에 흐름을 거절합니다.
기존 Windows scan 지원은 바뀌지 않습니다.

## 시연 실행

현재 소스 설치의 명령이 PATH에 있으면 어느 작업 디렉터리에서나 실행할 수 있습니다.

```bash
authzest fixture-demo --help
authzest fixture-demo
```

이 변경을 포함해 로컬에서 빌드한 실행 파일은 `authzest` 대신 정확한 파일 경로를 사용하세요.
대상 경로·bundle·모델·런타임 선택·자동 승인 옵션은 받지 않으며 `--help`만 제공합니다.
각 질문에 답하기 전에 표시된 근거·정확한 diff·식별값·한계를 읽으세요.
아래 식별값 자리표시는 그대로 입력하는 값이 아닙니다.

1. 화면에 표시된 정확한 `apply <proposal-id>`를 입력하면 해당 제안을 새 복사본에 적용합니다.
2. 적용 후 고정 소스 설정 계획을 검토하고 `verify <plan-id>`를 입력하면 별도로 해당 검사를
   승인합니다. 패치 적용은 검증 승인이 아닙니다.
3. 복구 미리보기를 검토하고 `restore <proposal-id>`를 입력하면 적용·검증 결정과 별도로
   복사본을 복구합니다.

Enter나 그 밖의 일치하지 않는 입력은 현재 단계를 거절합니다. `cancel`, EOF 또는 질문 입력 중
중단은 해당 단계를 취소합니다. 적용을 거절하면 검사·복구 전에 종료합니다. 검증을 거절하면
`not-run`으로 남기고 복구 여부는 계속 묻습니다. 복구를 거절하면 변경된 복사본을 유지합니다.
검사 실패는 성공한 수정이 아니며, 기록된 검사 실패 뒤에도 복구 여부를 별도로 묻습니다.

## 실행 범위와 남는 파일

별도로 승인한 고정 AST/소스 설정 worker만 자식 프로세스에서 실행합니다. 정확히 유지하는
fixture 바이트를 데이터로 읽어 debug 선언을 확인하고 fixture 소스를 import하거나 실행하지
않습니다. 미리보기는 고정 검사기·소스 해시·한계를 표시합니다. 이 명령은 모델·생성 테스트·
임의 명령·설치 hook·fixture 런타임 검사를 실행하지 않습니다.
별도 프로세스와 축소된 환경은 OS나 네트워크 sandbox가 아닙니다.

새 workspace·변경 전후 snapshot·로컬 기록은 확인할 수 있도록 남기며, 거절이나 실패 전에
생성한 파일도 유지합니다. 복구는 감지한 사후 편집을 덮어쓰지 않고 거절합니다.
작업 중 복사본을 동시에 편집하지 마세요. 중단되었거나 결과가 불확실하면 표시된 workspace를
확인하세요. journal은 충돌 후 자동 복구나 재시작/재개 기능이 아니며 임시 저장소는 영구 백업이
아닙니다.

`verify()` 호출 전에 검증 준비가 실패하면 세션은 `status: not-run`,
`reason: verification-setup-failed`, `execution_attempted: false`를 기록합니다.
복구 여부는 계속 별도로 묻고 명령은 `1`로 종료합니다. 해당 기록을 확실히 저장하지 못하면
대신 `reason: journal-unavailable`, `journal_status: unconfirmed`와 명시적인 경고를
표시합니다. 보존된 journal이 화면 결과와 일치한다고 가정하지 마세요. `verify()` 밖으로
예상하지 못한 예외가 전달되면 검사 결과를 만들어내지 않고 `workflow-failed`로 처리하며
자동 복구 질문도 보장하지 않습니다. 다음 조치 전에 보존된 workspace와 기록을 확인하세요.

workspace 생성 이후 초기화가 실패하거나 취소되면 확인된 생성 경로인 `workspace`와
제한된 `initialization_stage`를 확인 가능한 경우 보고합니다. 보존 파일은 삭제하지 않으며
기록이 없거나 불완전할 수 있습니다. 경로는 생성한 workspace를 식별할 뿐 현재 내용이나
세션 재개를 보장하지 않습니다. #65 이후 [#67](https://github.com/casing1/authzest/issues/67)은
이 실패 처리를 `codex-fixture`의 소스·런타임 모드와 개발용 런타임 스크립트로 확장합니다.
[미출시 실패 처리 상세](CODEX_FIXTURE.md#미출시-실패-처리)를 참고하세요.
`fixture-demo`의 질문 밖 중단은 `130`으로 종료하며 의도적인 질문 거절·취소 동작은 유지합니다.
이 소스 변경은 실행 범위를 확대하거나 공개 alpha.3 산출물을 갱신하지 않습니다.

mock 출처·실제 제공자 호출 0회·런타임 검증 `not-run`을 실제 모델 품질·인증된 사람의 동의·
인가 정확성·검증된 보안 수정과 혼동하지 마세요. 기존 복사본과 고정 검사 경계를 재사용하는
흐름이며 더 넓은 #35, 일반 저장소 변경과 생성 회귀 테스트 지원은 미완료입니다.

읽기 전용 [#63 제안 bundle](PROPOSAL_PREVIEW.md)은 이 명령의 실행기 입력이 아닙니다.
[예상 결과 manifest](../reference/EXPECTATION_CONTRACT.md)는 debug 설정이 아닌 정책/선언
목표를 설명하며 이 시연에 대한 승인으로 취급하지 않습니다.
개발 전용 `python -m scripts.demo_verify --runtime-check`는 계속 별도의 opt-in
[런타임 시연](RUNTIME_VERIFICATION.md)으로 남고 `fixture-demo`에는 이 옵션이 없습니다.
