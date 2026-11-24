<p align="center">
  <a href="../../../reference/REPOSITORY_HTTP_FILES.md">English</a> ·
  <strong>한국어</strong>
</p>

# HTTP 비공개 파일과 현재 입력 checkpoint

[문서 목차](../INDEX.md) · [확정 범위](../development/0.1.0-SCOPE.md) ·
[HTTP 사례](REPOSITORY_HTTP_VERIFICATION.md) · [HTTP 이미지 준비](REPOSITORY_HTTP_IMAGES.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## 제공 범위와 설계 경계

별도 Python 소스 API로 확정한 단일 파일 HTTP 배치, 현재 프로세스의 비공개 결정과 A 전용 봉인
입력을 구현합니다. 관리하는 origin·파일·guard 알고리즘을 활용하되 이전 v1.0/v1.1·생성 테스트·
T/A/B 검증기를 넓히지 않습니다. 외부 CLI/GUI 조작 흐름, Codex/Engine 접속, 소스 실행·HTTP 관찰이나
원본 수정은 구현하지 않습니다. `repo-suggest --http-poc`는 계속 제안 전용입니다.

파일 세션은 신뢰하는 호출자의 조정 도구입니다. 복사본 apply가 before/after 검사 실행이나 수정의
정확성을 뜻하지 않습니다. 후속 제품 조작 흐름은 별도의 현재 직접 phase 결과를 요구해야 합니다.
저장 계획·기록·snapshot·제공 비교가 그 권한을 대신하지 않습니다. 원본 최종 적용과 복구는 별도의
필수 후속 작업입니다.

## 정확한 소스 전용 복사 계획

`authzest.codex.repository_http_copy_plan`은 `RepositoryHttpCopyPlan`,
`prepare_repository_http_copy_plan(request, response, cases)`,
`validate_repository_http_copy_plan(plan, request, response, cases)`를 제공합니다.

schema 2.0 요청·응답 전체와 독립 사례·검사 계획을 검증하고 전체 식별자, 정확한 소스 전환과
호스트 diff를 결합합니다. 검증한 no-change/unknown/refused는 사례 없이 `None`을 반환할 수 있습니다.
변경 제안은 지정 독립 PoC 사례와 일치해야 합니다. 메타데이터를 재해시해도 현재 입력에서의 전체
재구성을 대신하지 못합니다. 계획에는 live root·결정·실제 파일 내용이 없으며 입출력을 하지 않습니다.

## 비공개 상태와 정확한 결정

`RepositoryHttpFileSession(origin, request, response, cases, copy_plan)`은 생성자 검증을 모두
통과한 뒤에만 기존 `RepositoryOrigin`의 소유권을 한 번 가져옵니다. 별도 schema 2.0 세션·계획·결정
식별자를 사용하며 새 비공개 트리를 최대 한 개 만듭니다.

```text
authzest-repository-http-<nonce>/
  project/<selected-flat-source.py>
  evidence/policy.txt
  evidence/source.before
  evidence/source.after
  record.json
```

파일 저장소는 정확히 이 일반 파일 다섯 개만 받습니다. context·생성 테스트·패키지 초기화 파일과
나머지 프로젝트 파일은 복사하지 않습니다. 디렉터리는 소유한 비공개 0700, 파일은 0600입니다.
선택한 비공개 소스와 journal만 교체할 수 있으며 원본 경로에는 쓰지 않습니다. 소스·전후 snapshot은
각 16 KiB, 정책은 8 KiB, host journal은 64 KiB로 제한합니다. 사례 기대값은 호스트에 남습니다.

별도 prepare/decide/perform 순서는 copy → accept-diff → apply → restore입니다. 각 단계는 정확한
현재 live 계획·결정 객체와 확인 문구, 한 번 사용, 최대 300초 조건을 요구합니다. 같은 준비를 반복해도
만료 시각을 연장하지 않습니다. 복사 전 원본의 연속성을 검사하고 효과·최종 쓰기 직전에 비공개 상태·
전체 계약·만료를 다시 검사합니다. 계획·문구가 사람·provider·정책 검토를 인증하지는 않습니다.

보유한 descriptor·이름·바이트로 일반 편집·같은 바이트의 inode 교체·alias·목록 변경을 거부합니다.
소스 교체 전에 pending 의도를 기록하고 정확한 재읽기·완료 journal로 확인된 revision을 결합합니다.
중단·불확실한 쓰기는 파일과 실제 commit/정리 관찰을 recovery-required 결과로 보존합니다.
자동 재시도·맹목적 rollback·저장 세션 열기·기존 트리 수용은 없습니다. close는 descriptor만 해제하고
산출물을 남깁니다. 동기 파일시스템 작업은 전체 시간 상한이나 악의적인 같은 사용자 쓰기에 대한
원자적 CAS가 아니므로 신뢰하는 호출자는 동시 쓰기를 배제해야 합니다.

## 현재 비공개 파일 checkpoint

내부 `_capture_runtime_checkpoint(phase)`는 pending 결정이 없는 copied-before 또는 applied-after
상태에서만 `_RepositoryHttpRuntimeCheckpoint`를 발급합니다. 실제 비공개 소스·정책·전후 근거·현재
전체 journal을 다시 읽고 전체 요청·응답·사례/검사/복사 계획, phase·세션/revision·root/파일 식별자를
결합합니다. 따라서 after checkpoint는 실제 적용한 비공개 파일을 관찰하며 제안 `after_text`만으로는
충분하지 않습니다.

같은 발급자의 `_recheck_runtime_checkpoint`는 자신이 발급한 정확한 현재 객체만 받고 파일을 다시
검사합니다. pending 결정, 후속 revision, close, 프로세스/스레드 변경, 복사·직렬화 객체와 다른 세션은
수용하지 않습니다. checkpoint는 내부 현재 파일 결합이며 실행 권한이나 runtime 결과가 아닙니다.
복사 후 원본이 바뀌어도 덮어쓸 권한이 생기지 않으며 원본 최종 적용에는 새 별도 검사가 필요합니다.

## A 전용 봉인 입력

`RepositoryHttpInputStage(session, request, response, cases, plan, phase)`는 정확한 발급자
checkpoint에 대해 HTTP·사례·계획 전체의 대응을 검증하고 다음만 봉인합니다.

```text
<private-stage>/
  input/manifest.json
  input/project/<selected-flat-source.py>
  record.json
```

입력 파일은 0444, 입력 디렉터리는 0555입니다. 바깥 디렉터리는 0700을 유지하고 0600 host 기록은
입력 밖에 둡니다. 별도 정책·정답·journal·생성 테스트·주변 인증정보 파일은 복사하지 않습니다.
선택한 소스는 기존 리터럴까지 그대로 보존합니다. B stage는 없으며
B에는 기존 요청 전용 schedule과 EOF만 제한된 stdin으로 전달합니다. 소스·정책·정답 mount는 없습니다.

할당 hook·재읽기·snapshot·create-plan은 사용 전후 비공개 파일과 봉인 파일을 재검사하며 builder가
예외를 내도 마찬가지입니다. 오래된 revision·편집·봉인 권한 변경·추가 항목·재진입·불확실한 정리를
거부하고 부분 산출물을 보존합니다. `prepare_create`는 현재 측정 입력 snapshot과 고정 A create-plan
선언을 담은 `RepositoryHttpStagedCreatePlan` 데이터만 반환하며 container를 만들거나 시작하지 않습니다.

## 남은 조작 흐름과 실제 수용

보고는 실행 not-run·인가 unknown·`verified_fix=false`를 유지합니다. 직접 관리하는 파일·가짜 callback
검사는 정책 정답·안전한 이미지·실제 수정 검증이 아닙니다. 구체적인 이미지/runtime 수용, Engine·중지
container 검사와 직접 host phase를 CLI 조작 흐름에 연결해야 합니다. 최종 원본 diff 승인·백업·편집
충돌 거부/복구, 설치형 실제 수용·저장 결과 표시는 #152/#150에 남아 있으며 이 API로 릴리스하지 않습니다.
