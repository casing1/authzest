<p align="center">
  <a href="../../../reference/REPOSITORY_HTTP_IMAGES.md">English</a> ·
  <strong>한국어</strong>
</p>

# HTTP 전용 A/B 이미지 준비

[문서 목차](../INDEX.md) · [확정 범위](../development/0.1.0-SCOPE.md) ·
[HTTP 검사](REPOSITORY_HTTP_VERIFICATION.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## 제공하는 경계

이 개발 소스 도구는 관리하는 이미지 입력을 검사하고 최소 비공개 context를 준비하며 제공된
비활성 rootfs 내보내기를 비교합니다. 역할은 **A/B**, 플랫폼은 **linux/arm64**만 지원합니다.
wheel 다운로드·설치, 이미지 빌드, Engine 접속, guest·대상 실행이나 프로젝트 패치를 하지 않습니다.
외부 `repo-suggest --http-poc` CLI는 계속 제안 전용입니다.

별도 schema 2.0 `repository-http-*` 보고와 context 객체를 사용하며 기존 generated-repair
이미지 검증기의 계약을 넓히지 않습니다. 제한된 파일·wheel·archive 기본 처리를 공유해도 이전
receipt가 HTTP 실행 권한이 되지는 않습니다.

## 고정 입력과 기존 wheel

`scripts.repository_http_image_inputs`는 `load_image_inputs`, `selected_inputs`,
`check_image_inputs`, `verify_wheelhouse`를 제공합니다. HTTP manifest는 참조한 의존성 manifest의
정확한 바이트, base 메타데이터, 역할별 의존성 폐쇄·lock, 관리하는 소스 자산, Dockerfile 바이트와
정규 recipe 해시를 결합합니다. 소스 경로와 HTTP guest root는 고정되며 외부 명령이나 임의 저장소
파일을 받지 않습니다.

wheel 검사는 이미 준비된 정확한 선택 wheelhouse를 읽습니다. 제한된 ZIP 구조·바이트 해시·
메타데이터·의존성 선언·호환 tag를 대조하고 wheel 코드를 import하지 않습니다. 추가·누락 파일,
변경 바이트, 지원하지 않는 링크와 잘못된 메타데이터를 거부합니다. 기존 의존성 자료를 재사용하며
대상 프로젝트의 의존성 해결기나 네트워크 설치기를 추가하지 않습니다.

개발 소스 checkout에서 실행합니다.

```bash
python -m scripts.repository_http_image_inputs
```

이 명령은 관리하는 입력만 관찰합니다. upstream 서명·이미지 식별·실제 runtime 설정·재현 가능한
빌드나 실행 이미지 수용을 입증하지 않습니다. 커밋된 이미지 manifest는 계속
`declared-not-built`이며 이미지 ID는 null, 준비·내용 검증 값은 false입니다.

## 보존하는 최소 비공개 context

`scripts.repository_http_image_context.prepare_image_context`는 저장소 root, 기존 wheelhouse,
기존 비공개 출력 부모, 역할과 플랫폼을 받습니다. 별도 `check_prepared_context`가 준비한 출력과
외부 receipt를 다시 대조합니다.

context에는 정확히 `Dockerfile`, `requirements.txt`, `assets/`, `wheels/`만 들어갑니다.
대상 소스·정책·독립 사례/정답·계정 자료·빌드 receipt·저장소 checkout을 넣지 않습니다. receipt는
context 옆에 둡니다. 새 디렉터리는 0700, 복사한 일반 파일은 0600입니다. 배타적 쓰기·descriptor
식별·정확한 재읽기·목록 검사로 경로 겹침·alias·입력 변경·추가 출력 항목을 거부합니다.

호출마다 새 bundle을 만듭니다. 실패 시 부분 출력을 보존하고 할당·소유권·descriptor 정리 불확실성을
구분합니다. 이전 bundle을 몰래 재사용하거나 삭제하지 않습니다. context 쓰기는 POSIX 소스 Python이
필요합니다. 신뢰하는 조작자는 같은 사용자 권한의 동시 쓰기를 배제해야 합니다. 동기 파일시스템
작업이 원자적 transaction이나 전체 파일시스템 시간 상한을 제공하지는 않습니다.

공개 Python 타입으로 다시 구성해도 context receipt는 과거 관찰 자료입니다. 파일 대조는 현재의
신뢰한 manifest 증명이나 빌드/실행 권한이 아닙니다. 후속 build 조작 흐름은 현재 관리 입력과 실제
선택 context 바이트를 구체적인 결정에 별도로 결합해야 합니다. 모든 준비 보고는 미빌드·미준비이며
실행·패치 권한을 부여하지 않습니다.

## 비활성 내용 비교

`scripts.repository_http_image_contents`는 제한된 `inventory_archive` 관찰을 재사용하며 별도
`compare_image_contents`를 제공합니다. TAR/ZIP을 풀거나 archive 링크를 호스트에서 따라가지
않습니다. catalog는 호출자가 제공한 관찰이며 인증한 이미지 식별이 아닙니다.

Docker가 관리하는 host/resolver 파일도 포함해 모든 baseline 항목을 보존하며 다음 추가만 허용합니다.

- `/opt/authzest-repository-http-guest` 아래의 관리 파일과 정확한 소유권·권한.
- A의 `/input/project` 또는 B의 `/input` 디렉터리 구조. 대상·테스트 파일은 넣지 않습니다.
- 선택한 고정 wheel payload와 설치 패키지 메타데이터. 추가 패키지는 거부합니다.

누락·추가, baseline 변경, 잘못된 바이트·종류·권한·소유권, 예상 밖 링크와 충돌을 거부합니다.
pip가 만드는 RECORD·entrypoint 내용은 별도 미검증 관찰로 남기며 timestamp·xattr·서명·실제
runtime 동작을 입증하지 않습니다.

비교가 성공해도 `contents_verified=false`, 이미지 설정·준비·실행 값 false, 인가 unknown,
`verified_fix=false`입니다. 가져온 보고가 현재 직접 관찰한 host/Engine 사실을 대신하지 않습니다.

## 다음 연결

구체적인 이미지 빌드·검사와 실제 이미지 수용은 미완료입니다. 새 HTTP 전용 파일 checkpoint,
봉인한 A 입력, Engine·중지 container 검사, 직접 before/after phase와
copy/diff/apply/restore CLI 조작 연결이 후속입니다. 원본 최종 승인·백업·동시 편집 거부·복구는
#152/#150의 필수 조건입니다. 이 오프라인 도구는 실제 생성·설치형 전체 수용·저장 결과 표시나
릴리스 기준을 완료하지 않습니다.
