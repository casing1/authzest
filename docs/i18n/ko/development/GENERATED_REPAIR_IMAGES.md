<p align="center">
  <a href="../../../development/GENERATED_REPAIR_IMAGES.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 이미지 (빌드한 이미지가 아닌 고정 입력)

[문서 목록](../INDEX.md) · [Guest 진입점](GENERATED_REPAIR_GUESTS.md) ·
[런타임 메타데이터](GENERATED_REPAIR_PREFLIGHT.md)

## 범위 (2026-11-15 KST)

이 [#152](https://github.com/casing1/authzest/issues/152) 부분 기반은 분리된 T/테스트, A/애플리케이션,
B/relay 역할의 이미지 후보 입력을 기록합니다. 오프라인 입력 검사·비공개 context 준비·호스트 archive
비교를 추가하며 빌더나 활성 생성 코드 실행기는 추가하지 않습니다. #152는 열린 상태입니다. Manifest의
`status: "candidate-not-built"`, `image_ids: null`, `contents_verified: false`를 유지하며 입력 일치로
준비된 이미지나 살아 있는 profile을 만들어내지 않습니다.

저장소 helper는 build·pull·load·layer 가져오기·컨테이너 생성/시작·생성 코드 실행·Docker CLI/Engine
요청·AI 호출을 수행하지 않습니다. 새 공개 AuthZest 명령·런타임 결정·릴리스도 추가하지 않습니다.
운영자 로컬 receipt는 별도 비공개 기록이며 이식 가능한 manifest의 빌드 전 후보 상태를 대체하지 않습니다.

[CLI 파일 흐름](../guides/GENERATED_FILE_WORKFLOW.md)은 기존 비공개 phase를 개별 결정하는 단계에
연결합니다. 필수 pre-import 커널 guard가 공통 자산·T/A/B launcher를 바꿔 platform recipe 6개의
해시를 갱신합니다. 현재 재빌드/검토 이미지가 필요하며 의존성 lock은 그대로입니다. 이전 profile에
새 선언 해시를 넣어도 이미지가 갱신·검증되지 않습니다. 비공개 loader는 계정 사용 전·각 dispatch 전에
현재 관리 recipe/lock/자산 결합을 확인하지만 이를 런타임 준비 완료로 취급하지 않습니다.

네트워크 guard 수정은 엄격한 lo-only 수용을 유지하며 관리하는 기본 tunnel fallback의 정확한
이름/type/flag 조합만 추가합니다. Non-loopback fallback은 관리상 DOWN·operstate DOWN·iflink0,
양수이며 서로 다른 index와 고정 proc/sysfs 사실의 제한된 전후 일치 조건을 만족해야 합니다.
socket/netlink·NET_ADMIN·sysctl·network template 변경은 없습니다. 관찰은 진입 시 활성
non-loopback interface가 없었다는 범위뿐이며 주소/route·실제 외부 연결성 측정·격리 증명이 아닙니다.
공유 common 자산과 recipe6개 pin이 다시 바뀌어 현재 재빌드/검토한 T/A/B 이미지와 설치형 수용은
남아 있습니다. 고정 의존성과 기본 생성 경로는 그대로입니다.

## 기록한 후보 입력

소스의 [runtime/generated_repair/images](../../../../runtime/generated_repair/images/)에는
[manifest](../../../../runtime/generated_repair/images/manifest.json) 하나, platform/역할별 dependency
lock 6개, Dockerfile recipe 6개, 보존한 원본 base-image JSON 5개가 있습니다. 후보 base는
`docker.io/library/python:3.12.16-slim-bookworm`이며 recipe는 변경 가능한 tag가 아니라 각 platform의
기록한 child manifest digest를 사용합니다.

| 역할 | platform별 추가 고정 wheel | 의도한 역할                                         |
| ---- | -------------------------- | --------------------------------------------------- |
| T    | 20                         | FastAPI 애플리케이션과 생성 pytest 테스트           |
| A    | 14                         | 고정 guest launcher가 제공하는 FastAPI 애플리케이션 |
| B    | 0                          | base Python 표준 라이브러리를 사용하는 관리형 relay |

`linux/amd64`, `linux/arm64` 모두 명시적 입력을 갖고 선택한 dependency 집합의 package 이름 합집합은
22개입니다. B가 wheel을 추가하지 않는다는 뜻이며 base OS·Python 설치·상속한 파일이 의존성이 없거나
검증됐다는 뜻은 아닙니다.

Guest 후보는 검토한 release metadata에서 `pytest==9.0.3`을 선택합니다. 호스트 개발 환경과 별개이며
기존 호스트 pytest 제약은 바꾸지 않습니다. 고정 guest launcher는 `-c /dev/null`과 정확한 테스트
선택을 유지합니다. 이미지 입력은 테스트 탐색을 확대하거나 모델이 선택한 의존성을 추가하지 않습니다.
별도 커널 guard가 launcher 소스를 변경하며 선택 의존성 버전은 그대로입니다.

## 오프라인 검사가 확인하는 범위

[scripts/generated_image_inputs.py](../../../../scripts/generated_image_inputs.py)는 닫힌 manifest,
역할/platform 집합, package metadata와 dependency 선택을 유지관리 소스와 대조합니다. 기록한 원본
OCI/Docker JSON 바이트는 선언한 index → 선택 child manifest → config digest 연결과 일치해야 합니다.
index는 선언한 Linux architecture/variant를 선택하며 선택 config는 OS/architecture와 기록한 정확한 Python 환경 결합에 맞아야 합니다.
현재 guest 자산의 바이트, 해시 고정 lock 텍스트와 고정 Dockerfile recipe도 비교합니다.

이는 입력 식별자·일관성 검사입니다. 보존한 upstream 문서나 wheel 선언이 발행자를 인증하거나 서명을
검증하거나 공급망 출처를 입증하지 않습니다. 같은 기록 입력의 digest와 일치한다는 사실은 이미지 내부
파일의 독립적 증거가 아닙니다. 이 입력 검사는 root filesystem layer나 완성한 이미지를 검사하지
않으며 아래의 별도 호스트 archive 비교는 더 좁고 명시적인 관찰 범위만 갖습니다.

향후 recipe는 저장소 checkout·사용자 파일·살아 있는 workspace 대신 선택한 `requirements.txt`,
`wheels/`, 고정 `assets/`만 있는 최소 준비 context를 기대합니다. T/A는 네트워크 비활성,
`--no-index`, `--no-deps`, `--require-hashes`를 사용하는 wheel 전용 설치를 기술하며 B는 package를
설치하지 않습니다. 검사 중 Dockerfile 지시는 비활성 텍스트이고 flag는 관찰한 빌드 격리·런타임 제약이
아닙니다. 아래 context helper가 이 입력을 파일로 준비하며 검토한 build/provisioning·결과 로컬
image ID 검증은 별도 운영 작업입니다.

## 개발 checkout에서 검사

소스 개발 환경을 설치한 뒤 다음을 실행합니다.

```bash
python -m scripts.generated_image_inputs --check
```

기본 동작도 같은 오프라인 검사입니다. 로컬 후보 입력을 읽어 JSON 요약을 출력하며 wheel 다운로드·
registry/Engine 접속·Dockerfile 실행·wheel 코드 import는 하지 않습니다. 성공 요약도 빌드하지 않은
후보를 설명할 뿐 실행 권한을 부여하지 않습니다.

선택적 Python API `verify_wheelhouse(root, wheelhouse, role, platform)`는 명시적으로 제공한 기존 wheel
디렉터리를 받습니다. 정확한 선택 파일 이름, 제한된 일반 파일 바이트·크기/digest, 비활성 wheel ZIP
metadata를 검사하며 다운로드·설치·import는 하지 않습니다. 이 추가 바이트 관찰도 서명·이미지 내부
내용·비트 단위 재현 빌드·효과적 resource 제약·검증된 수정을 입증하지 않습니다.

## 새 비공개 build context

빌드 client의 Docker 설정은 [파일 흐름 안내](../guides/GENERATED_FILE_WORKFLOW.md)의 엄격한 runtime
전용 설정과 분리합니다.

[scripts/generated_image_context.py](../../../../scripts/generated_image_context.py)는
`prepare_image_context(repo, wheelhouse, parent, role, platform)`를 제공합니다. 먼저 입력 manifest와
정확한 기존 wheel 집합을 재검사한 뒤 호출자가 제공한 기존 비공개·소유 parent 아래 새 비공개 bundle을
만듭니다. Parent는 소스 저장소·wheelhouse와 분리돼야 합니다. 출력 생성에는 지원하는 POSIX Python
소스 환경이 필요하며 Windows 쓰기는 미지원입니다. 두 선언 platform의 비활성 입력은 준비할 수 있지만
platform 간 실제 빌드 수용을 의미하지 않습니다.

Build context는 `Dockerfile`, `requirements.txt`, `wheels/`, 역할별 고정 `assets/`만 포함하며 B는
빈 wheel lock의 주석을 유지합니다. 애플리케이션·생성 테스트·oracle·workspace 기록·계정 데이터·저장소
checkout은 포함하지 않습니다. Context 디렉터리는 `0700`, 일반 single-link 파일은 `0600`이며 wheel
바이트는 불투명 파일로 복사하며 코드를 import하거나 payload를 호스트 디렉터리에 풀지 않습니다.

불변 `PreparedImageContext` 결과는 build context **밖**의 `receipt.json`을 가리킵니다. Inventory는
소스 경로 없이 상대 이름·크기·해시·파일 식별자·manifest/recipe/lock 결합을 기록합니다.
`check_prepared_context(context_path, receipt)`는 향후 운영 호출자가 사용하기 전 정확한 트리·바이트·
권한·식별자·외부 기록을 재검사합니다. 추가 파일·변경된 링크/권한·불일치 기록을 거부합니다. Receipt는
과거 데이터이며 빌드 권한·발행자 인증·악의적 로컬 동시 쓰기 방어 증거가 아닙니다.

준비 과정은 충돌 대상을 재사용하거나 실패한 할당을 재시도하거나 부분 출력을 삭제하지 않습니다.
실패 시 시도/확인한 bundle·부분 inventory를 보존하고 할당·descriptor close 불확실성을 구분합니다.
Build·runtime·readiness flag는 false이며 helper에 Docker 호출·새 공개 CLI는 없습니다.

## 호스트 archive 목록과 선택한 내용 비교

[scripts/generated_image_contents.py](../../../../scripts/generated_image_contents.py)는 명시적으로
제공한 로컬의 압축하지 않은 rootfs tar 파일을 처리합니다. `inventory_archive(path)`는 제한된 chunk로
경로·종류·권한·소유자·크기·파일 해시·제한된 distribution metadata를 불변 `ArchiveCatalog`에 기록합니다.
항목을 압축 해제하거나 호스트에서 링크를 따라가거나 코드를 import하거나 Engine에 접속하거나
컨테이너를 export하지 않습니다. Catalog는 전달한 관찰값이지 인증된 이미지 식별자·실행 권한이 아닙니다.

`compare_image_contents(repo, base_catalog, role_catalog, wheelhouse, role, platform)`는 현재
`linux/arm64` T/A/B 비교만 지원합니다. 입력/wheel 검사를 재사용하고 제공한 base 목록·관리하는 guest
자산·일반 wheel payload·설치된 distribution metadata를 비교하며 누락·충돌·예상 밖 추가를 거부합니다.
호스트에 이식 가능한 데이터 비교이며 Windows나 추가 platform의 런타임 지원이 아닙니다. 관찰한
Docker 관리 파일 `etc/hostname`, `etc/hosts`, `etc/resolv.conf`도 다른 baseline 항목처럼 제공한 base의
바이트와 metadata에 일치해야 합니다. 비교한 파일로 나열하며 비교 대상에서 제외하지 않습니다.

성공 시 `baseline_unchanged`, `wheel_payloads_verified`, `maintained_assets_verified`,
`installed_package_metadata_verified` 같은 세분화된 사실을 보고합니다. Pip이 만드는 `RECORD`와
entrypoint script의 경로·해시는 `unverified_generated_files`에 남기며 내부 내용은 **독립적으로 검증하지
않습니다**. 전달한 base catalog만으로 선언한 base 이미지에서 export했다는 사실을 입증하지 못합니다.
Timestamp·확장 속성·서명·이미지 config·효과적 런타임 동작도 입증하지 않습니다. 따라서 선택 비교가
성공해도 `contents_verified`, `image_configuration_verified`, `runtime_ready`, `runtime_invoked`,
`execution_authorized`는 false입니다.

## 분리된 Engine bootstrap과 남은 조건

비공개 [Engine metadata bootstrap](GENERATED_REPAIR_PREFLIGHT.md)은 이미지 ID나 기대 daemon
식별자를 만들어내지 않고 version/info 관찰을 표현합니다. `/version`과 고정 `/v1.51/info`만 사용하며
광고한 API 범위가 미지원이면 두 번째 요청 전에 거부합니다. Engine 식별자는 관찰했지만 고정하지 않은
상태이고 전체 runtime profile 생성·이미지 검사·executor 활성화는 하지 않습니다. 공개 CLI 흐름도
아닙니다.

정지 생성 inspect·현재 입력/세션 결정·제한 실행/수집·정확한 guest 정리는 소스로 구현했습니다.
실제 활성 수용 전에는 현재 검토한 이미지 준비/내용·로컬 image ID·커널 실현 가능성과 설치형
before/after/restore 수용이 필요하며 로컬 결과 UI도 남아 있습니다. `ready`·실행 권한·수정 검증은 성립하지 않습니다. #89 위험 수용·#152
완료·버전 변경·릴리스 권한은 이 문서에 포함하지 않습니다.
