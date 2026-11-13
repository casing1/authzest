<p align="center">
  <a href="../../../development/GENERATED_REPAIR_RUNTIME_PROFILE.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 runtime profile — 오프라인 선언과 생성 계획

[문서 목차](../INDEX.md) · [Guest 소스](GENERATED_REPAIR_GUESTS.md) ·
[생명주기 모델](GENERATED_REPAIR_LIFECYCLE.md)

## 범위 — 2026-11-13 KST

이번 [#152](https://github.com/casing1/authzest/issues/152) 부분 단계는 전달받은 로컬 엔진/이미지
선언을 검증하고 고정된 **정지 생성 인자 데이터**를 만듭니다. Docker 실행·daemon/이미지/파일 검사·
의존성 준비·컨테이너 생성/시작·생성 코드 실행·executor/세션 활성화는 하지 않습니다. #152는 OPEN이며
유효한 profile이 런타임 준비 완료를 뜻하지 않습니다.

비공개 소스 API는 `RuntimeProfile`, `ContainerCreatePlan`, `validate_runtime_profile`,
`build_container_create_plan`을 제공합니다. 호출자가 profile/plan을 구성·가져올 수 있으므로 미검증
데이터이지 동의·증명·재사용 가능한 실제 세션·before 근거가 아닙니다. builder는 wrapper 타입만 믿지
않고 전달 profile 내용을 다시 검증합니다.

## 결합한 선언이지 관찰한 식별자가 아님

닫힌 profile은 절대 Docker 실행 파일과 SHA-256, 명시적 로컬 Unix 소켓 하나, 소유 Docker 설정
폴더, 정확한 빈 JSON 설정(`{}\n`)의 해시, daemon 식별 해시와 명시적 API 버전을 선언합니다.
`linux/amd64` 또는 `linux/arm64`, T/A/B의 고정 로컬 이미지 ID·의존성 lock/recipe 해시·관리형
guest 자산의 정확한 예상값도 선언합니다. tag·자동 모델/플랫폼 대체·호출자 선택 명령은 지원하지 않습니다.

guest 예상 해시는 현재 관리하는 소스와 결합하지만 전달 이미지가 실제 해당 파일을 포함한다는 증명이
아닙니다. 이미지 ENV·entry point·시작 hook·익명 volume·아키텍처·의존성·내용은 별도의 검토한
운영 검사로 확인해야 합니다. 이번 변경은 실제 이미지 ID·의존성 lock·지원 daemon 버전을 제공하지 않습니다.

템플릿은 명시적 Docker `--config`와 `--host`를 선택하며 제안한 subprocess 환경에는 선언한
`DOCKER_API_VERSION`만 둡니다. HOME/PATH·proxy·context·TLS·자격증명·대체 설정 변수는 상속하지
않습니다. API `1.41`~`1.99`는 선언 문법 범위이지 모든 엔진/버전의 테스트·사용 가능성을 뜻하지 않습니다.

추후 호출자가 빈 설정 폴더/파일을 만들고 식별자를 검사하며 다른 항목·편집을 거부해야 합니다.
설정 해시 선언만으로 symlink·교체·proxy 설정·credential helper가 차단되지 않습니다. Unix endpoint도
다른 곳에 중계할 수 있으므로 로컬 문법이 신뢰 로컬 daemon·소켓 식별자·권한 경계를 입증하지 않습니다.

## 고정 역할 계획

| 역할 | 읽기 전용 소스 mount                                | 네트워크                              | 고정 guest 진입점   |
| ---- | --------------------------------------------------- | ------------------------------------- | ------------------- |
| T    | 선언 staging root에서 파생한 app·생성 테스트 파일만 | none                                  | `test_launcher.py`  |
| A    | 같은 root의 app 파일만                              | none                                  | `app_launcher.py`   |
| B    | 없음; app/test/staging 인자 거부                    | 정확한 전체 A 컨테이너 ID namespace만 | `relay_launcher.py` |

T/A 입력은 고정 leaf에서 파생하며 임의 파일별 mount 인자를 받지 않습니다. 경로는 제한된 ASCII의
정규 절대 경로만 허용하고 shell이 없어도 comma·제어 문자·상위 이동 등 mount 문법의 모호함을
거부합니다. staging 경로/해시도 선언일 뿐 실제 캡처·비공개·미변경·소유·checkout 외부 여부를
확인하지 않습니다. B는 남은 1~40,000 밀리초만 받고 호스트 절대 시계 기준을 받지 않습니다.

이름과 고정 label은 제한된 세션/역할 hex nonce에서만 파생합니다. 추후 호스트는 새 nonce를 만들고
생성 전에 소유 이름을 영속 기록해야 하며 호출자의 재사용 nonce는 새로움의 증명이 아닙니다.
고정 인자 템플릿은 `container create`·pull-never·UID/GID 65532·read-only root·cap-drop-all·
no-new-privileges·private IPC/cgroup namespace·init/restart/logging/healthcheck/TTY/interactive/
port 공개 비활성·고정 tmpfs를 선택합니다. CPU/memory/swap/PID/shm 예산은 기존 설계를 유지하며
진입점은 고정 `/usr/local/bin/python -I -B`와 역할 스크립트입니다.

이는 제안 flag이지 **효과적 런타임 강제가 아닙니다**. 확인하지 않은 private-PID/default seccomp
flag를 만들지 않으며 실제 기본/효과적 PID 격리·seccomp·controller·runtime·mount·volume·네트워크·
제한은 지원하는 정지 컨테이너 profile과 대조해야 합니다. 이번에는 start/attach/stop/remove 인자
builder·전송·자동 정리도 없습니다.

## 결과와 남은 조건

계획은 `planned-not-executed`, 출처 `caller-supplied-unverified`, `runtime_invoked: false`,
`execution_authorized: false`, 인가 `unknown`, `verified_fix: false`입니다. 이 데이터나 일치하는
모의 검사로 실행·쓰기 권한을 열지 않습니다. 원래 호스트 phase/준비/정리 제한을 유지하고 여기서는
timer도 시작하지 않습니다.

검토한 client/socket/config/daemon 식별자와 이미지/lock, 효과적 제약, 실제 안전 입력 staging,
정지 생성 검사, 제한 attach/start/준비/capture와 guest 정리 확인, 영속 근거·세션 결정·정확한 설치
인수 검증은 남았습니다. 새 제공자/소스 공유·운영 적용/복구·이슈 완료·위험 수용·릴리스는 없습니다.

참고: [Docker create](https://docs.docker.com/reference/cli/docker/container/create/),
[Docker CLI configuration](https://docs.docker.com/reference/cli/docker/),
[Docker seccomp](https://docs.docker.com/engine/security/seccomp/).
