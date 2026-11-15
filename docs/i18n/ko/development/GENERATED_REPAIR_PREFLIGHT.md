<p align="center">
  <a href="../../../development/GENERATED_REPAIR_PREFLIGHT.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 런타임 메타데이터 — 고정 로컬 Engine 조회

[문서 목록](../INDEX.md) · [Runtime profile](GENERATED_REPAIR_RUNTIME_PROFILE.md) ·
[입력 staging](GENERATED_REPAIR_STAGING.md)

## 범위 — 2026-11-15 KST

이 [#152](https://github.com/casing1/authzest/issues/152) 부분 구현은 비공개 로컬 Engine 메타데이터
reader와 제한된 전달 데이터 비교기를 추가합니다. 오프라인 회귀 검사의 소켓·endpoint 정보·시계는
가짜이며 회귀 검사에서 실제 엔진·plugin·소켓·생성 코드·AI는 호출하지 않습니다. 기존 executor,
lifecycle 모의 모델·세션·공개 CLI에는 연결하지 않습니다. #152는 열려 있으며 실제 PoC나 수정 검증
완료가 아닙니다.

## 전용 Engine transport를 사용하는 이유

Docker CLI `v29.0.0`의 `docker info`는 format 처리 전 `ListPlugins`를 호출하고, 빈 `--config` 밖의
시스템 경로를 포함한 설치 plugin 바이너리로 metadata를 요청합니다. JSON template이나 닫힌 환경만으로
이 경로를 없앨 수 없습니다. CLI `info`, 주변 설정을 탐색하는 SDK, `curl`, shell·보조 실행 파일을
사용하지 않습니다.

reader는 profile의 명시적 Unix endpoint와 다음 고정 GET만 사용합니다.

| 작업                | 고정 요청                                                    |
| ------------------- | ------------------------------------------------------------ |
| 버전                | `/version`                                                   |
| 엔진 정보           | `/v<declared API>/info`                                      |
| T, A, B 이미지 정보 | `/v<declared API>/images/<that role's exact sha256 ID>/json` |

호출자가 method·경로·header·tag·query를 선택할 수 없으며 redirect·proxy·DNS·재시도·build·pull·install·
컨테이너 create/start·호스트 우회 실행은 없습니다. CLI plugin 실행 경로를 피하는 것이며 Unix endpoint의
신뢰나 다른 곳으로 전달되지 않음을 입증하는 것은 아닙니다.

## 전송 한도와 현재 endpoint

연결 전과 close 후에 symlink가 아닌 부모 경로의 핵심 식별자와 소켓 전체 식별자를 확인합니다. 신뢰한
OS 가정하에 현재 사용자/root 소켓만 받아들이며 공유 sticky 부모 경로는 허용할 수 있습니다. 반환 pin은
소켓 식별자 9개 필드와 제한된 부모 경로 digest를 포함하고 응답 5개 모두 같아야 합니다. 변경 탐지이며
악의적인 동일 사용자 동시 쓰기에 대한 원자성이나 인증된 peer/daemon 출처를 보장하지 않습니다.

호출자가 보유한 원래 setup·phase 절대 마감을 전체 순서에 적용하고 조회마다 갱신하지 않습니다. 기존
제안 한도는 원래 40초 phase 안의 누적 setup/readiness 10초이며, 후속 세션이 앞선 작업량도 계산해야
합니다. 동기 coordinator hook을 매 연결 직전에 다시 확인하지만 동의나 재사용 가능한 실행 결정은
아닙니다. 동기 OS 호출 전체의 선점 시간 보장은 없으며 소켓 close를 별도 guest 정리 시간으로 보지 않습니다.

HTTP header는 요청당 16 KiB/32개, body는 64 KiB이며 framing을 포함한 원시 응답 전체가 조회 5개에
공유 256 KiB 한도를 사용합니다. Content-Length, 엄격한 chunked 또는 연결 종료 body만 받아들이고
정확한 framing 완료와 EOF가 필요합니다. 충돌·중복 header, 미지원 encoding, 잘림·추가 바이트·한도/마감
초과는 거부합니다. 할당·연결·요청·close 불확실성을 구분하고 최초 실패/취소를 보존하며 정리 성공이
앞선 실패를 지우지 않습니다.

## 메타데이터 비교와 실행 준비의 구별

`normalize_runtime_metadata`는 정확한 순서의 응답 객체 5개와 제한된 JSON만 받습니다. 전달 프레임은
호출자가 제공한 데이터입니다. `observe_runtime_metadata`는 고정 reader를 조정하고 query 시도와 실제
contact 시도를 구분합니다. 가짜를 주입해도 인증된 관찰이 되지 않으며 비활성 executor를 바꾸거나
살아 있는 세션 권한을 만들지 않습니다.

광고된 API 범위·Linux platform·version/info의 서버 버전 일치·선언한 엔진 식별자·역할별 정확한
이미지 ID/architecture를 대조합니다. 엔진 식별자의 preimage는 `schema_version: "1.0"`,
`kind: "generated-repair-engine-identity"`와 `/info`의 `ID`를 `engine_id`로 담은 canonical JSON이며,
UTF-8 SHA-256이 profile 선언과 같아야 합니다.

제한된 선택 메타데이터와 body hash만 보존합니다. 이미지 config·daemon security option·cgroup 필드는
**메타데이터에서 읽은 선언**이며 실제 resource·seccomp·namespace/mount 제약이나 이미지 내부 파일
증거가 아닙니다. ID/label 일치가 dependency lock·recipe·유지관리 guest 자산을 검증하지 않습니다.
모의 검사를 근거로 실제 지원 Engine 버전·이미지 집합을 만들어내지 않습니다. reader가 CLI를 실행하지
않으므로 로컬 CLI 바이너리·설정 식별자도 관찰되지 않은 상태입니다.

별도 [호스트 archive 비교](GENERATED_REPAIR_IMAGES.md)는 제공한 rootfs catalog를 압축 해제·실행하지
않고 관리형 자산·정확한 wheel payload와 비교할 수 있습니다. 세분화된 파일 관찰을 보고하고 검증하지
않은 pip 생성 파일을 보존하며, 일치해도 전체 내용/config/readiness는 false입니다. 메타데이터 reader
결과는 이 파일 관찰을 대체하지 않으며 두 helper 모두 제공한 export의 이미지 신원을 인증하지 않습니다.

결과의 `ready`, `execution_authorized`, `verified_fix`는 false, authorization은 unknown이며 생성
runtime은 미실행입니다. 출력 JSON은 과거 데이터이지 재개 가능한 영수증·before 근거가 아닙니다.
원시 daemon 정보·로컬 endpoint 상세는 비공개로 유지해야 하며 자동 공개 업로드는 추가하지 않습니다.

## 남은 연결 작업

### 이미지 ID를 만들지 않는 endpoint 전용 bootstrap

비공개 `_generated_repair_bootstrap.py` API는 전달 프레임 2개의 `normalize_engine_bootstrap`과 고정
reader용 `observe_engine_bootstrap`을 제공합니다. 명시적인 canonical Unix endpoint를 받으며 전체
`RuntimeProfile`은 생성하지 않습니다. `GET /version` 다음 고정 `GET /v1.51/info`만 허용하고 두 번째
조회 전 광고한 최소/최대 API 범위에 `1.51`이 포함돼야 합니다. 미지원 API/platform이면 협상·재시도
없이 중단합니다.

두 조회는 원래 setup/phase 마감과 256 KiB wire 예산을 공유합니다. 첫 응답의 endpoint pin을 두 번째
조회 trusted hook 전후·연결 전에 재검사하고 반환 pin도 같아야 합니다. 소켓 정리가 guest 정리나
peer 신원을 성립시키지는 않습니다.

별도 bootstrap 결과는 관찰했지만 **고정하지 않은** engine 식별자/hash를 기록합니다.
`profile_created`, `images_inspected`, `identity_pinned`, `ready`, `execution_authorized`,
`verified_fix`는 false입니다. 이미지 ID·recipe/lock 내부·효과적 capability 증거·공개 CLI 흐름은 제공하지 않습니다.
[고정 이미지 후보 입력](GENERATED_REPAIR_IMAGES.md)은 분리된 오프라인 소스 검사이며 준비된 이미지
집합이 아닙니다. 로컬 endpoint/daemon 관찰은 비공개이며 운영 기록 공개를 이 가이드에 추가하지 않습니다.

### 런타임 수용은 미완료

실제 호환성·검토한 이미지 준비/내용·정지 컨테이너의 효과적 제약 확인, 제한된 attach/start/capture와
정확한 guest 정리, 영속 세션 결정·설치형 generation/before/apply/after/restore 수용·읽기 전용 결과 UI는
남아 있습니다. #89 위험 수용·이슈 완료·버전 변경·릴리스도 수행하지 않습니다.

근거: [Docker CLI info 소스](https://github.com/docker/cli/blob/v29.0.0/cli/command/system/info.go#L78-L105),
[metadata 실행](https://github.com/docker/cli/blob/v29.0.0/cli-plugins/manager/candidate.go#L16-L18),
[시스템 plugin 경로](https://github.com/docker/cli/blob/v29.0.0/cli-plugins/manager/manager_unix.go#L13-L18),
[Engine API 명세](https://docs.docker.com/reference/api/engine/version/v1.51/).
