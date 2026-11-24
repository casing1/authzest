<p align="center">
  <a href="../../../reference/REPOSITORY_HTTP_RUNTIME.md">English</a> ·
  <strong>한국어</strong>
</p>

# HTTP runtime 입력과 메타데이터 검사

[문서 목차](../INDEX.md) · [확정 범위](../development/0.1.0-SCOPE.md) ·
[HTTP 비공개 파일](REPOSITORY_HTTP_FILES.md) · [HTTP 이미지 준비](REPOSITORY_HTTP_IMAGES.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## 제공 범위

이 비공개 소스 API는 별도 schema 2.0 HTTP A/B runtime을 준비하며 이전 v1.0/v1.1·T/A/B 검증기를
유지합니다. 외부 CLI는 계속 제안 전용으로 이 API를 호출하거나 guest를 생성·시작하거나 원본을
수정하지 않습니다. 테스트는 직접 관리하는 비활성 파일·메모리 소켓·제공 메타데이터를 사용하며
이번 전달에서 실제 Engine·모델·이미지·대상을 사용하지 않습니다.

비공개 메타데이터 reader는 신뢰하는 조정자가 명시적으로 호출하면 선언된 Unix Engine endpoint에
접속할 수 있습니다. 모듈 import·프로필 읽기·제공 자료 비교는 reader를 호출하지 않습니다.
reader는 고정 GET 메타데이터 요청만 보내며 이미지 준비나 컨테이너 생명주기를 제어하지 않습니다.
선언·보고의 일치는 이미지 내용·커널 강제·인가·정책 정답·직접 전후 실행·쓰기 허가를 입증하지 않습니다.

## 비공개 프로필과 client 연속성

`_repository_http_runtime_input`은 크기가 제한된 비공개 HTTP 프로필 파일만
`LoadedRepositoryHttpRuntimeProfile`로 읽습니다. 별도 `RepositoryHttpRuntimeProfile`, 관리하는
arm64 A/B recipe·lock·자산과 기존 빈 설정 해시를 요구하며 이전 프로필·T 역할·중복 필드·잘못된
인코딩·초과 크기를 거부합니다.

nofollow descriptor를 유지하고 안전한 상위 디렉터리, 비공개 단일 링크 파일의 권한·소유권·전체
바이트·식별자를 검사합니다. `assert_current()`에서 반복 확인하며 일반 편집과 같은 바이트의 파일
교체도 handle을 무효화합니다. 종료는 파일을 보존하고 descriptor를 해제하며 불확실한 정리는 그대로
기록합니다. 분리된 검토 자료로 현재 handle을 다시 열거나 runtime 권한을 얻을 수 없습니다.
POSIX non-frozen 소스 설치가 필요합니다.

별도 HTTP client pin은 호출자의 최초 동기식 기한 검사를 사용해 선언된 Docker 실행 파일, 정확한
비공개 빈 설정과 endpoint 식별자를 대조합니다. 실행 파일을 시작하거나 소켓에 접속하지 않고
바이트·권한·구성원·식별자를 검사합니다. 후속 조작 흐름은 각 효과 전후에 현재 프로필과 비공개 입력의
연속성을 별도로 확인해야 합니다. 동기식 파일 검사는 적대적인 동일 사용자 쓰기에 대한 원자적 CAS나
전체 파일시스템 시간 상한이 아닙니다.

## 네 개의 고정 Engine 문서

`_repository_http_engine_http.read_engine`은 새 프로필과 `version`, `info`, `image-A`, `image-B`만
허용합니다. T 조회·임의 URL·body 업로드·재시도·대체 경로는 없으며 이전 reader의 제한된 HTTP
프레이밍·시계·endpoint 기본 도구를 변경 없이 공유합니다.

- 호출자가 유지하는 누적 wire 예산과 최초 기한을 사용하며 요청마다 새 허용량을 주지 않습니다.
- 접속 전후 Unix endpoint·상위 경로 식별자를 검사하고 전송 직전에 현재 동기식 guard를 확인합니다.
- 엄격한 크기·프레이밍·body·시간 검사와 소켓 정리 사실을 유지합니다. handle 획득 불확실성,
  중단·초과/잘린 응답·close 실패도 구분합니다.

`_repository_http_preflight.normalize_runtime_metadata`는 제공된 정확히 네 응답을 비교합니다.
비공개 `observe_runtime_metadata`는 최초 phase 40초와 누적 setup 10초 안에서 같은 네 문서를
조회합니다. 전체 현재 프로필, daemon·API·플랫폼, A/B 이미지 ID, endpoint 식별자와 크기가 제한된
이미지 설정을 결합합니다. 기존 daemon ID 해시 규칙을 유지하지만 daemon 인증은 아닙니다.

별도 식별자를 가진 schema 2.0 HTTP 관찰을 반환합니다. 부분 실패는 검증된 앞부분과 조회·접속·정리
진단 및 사용한 wire 크기를 유지합니다. 일치해도 readiness는 false, 인가는 unknown, verified-fix는
false입니다. 제공 응답·직렬화 관찰은 검증되지 않은 기록이며 직접 읽은 daemon 메타데이터도 이미지
내용이나 커널 자원·격리 강제를 입증하지 않습니다.

image-inspect의 `Id`는 configuration digest입니다. 선택적인 `Descriptor`는 별도
`manifest_descriptor`로 투영하며 명시적으로 보고한 플랫폼이 일치하는 image manifest일 때만
`platform_manifest_reported`를 true로 둡니다. 없는 descriptor는 `null`로 유지합니다. index/list나
플랫폼이 없는 descriptor는 해당 플랫폼 pin을 제공하지 않으며 configuration ID로 대체하지 않습니다.

## 시작 전 컨테이너 비교

`_repository_http_container_inspect.validate_stopped_container`는 정확한
`RepositoryHttpCreatePlan`과 제한된 Engine 객체 또는 원소 하나의 CLI 배열을 받습니다.
전체 프로필·manifest 또는 요청 전용 schedule·생성 계획을 재구성한 뒤 비교합니다.
변경한 자료의 해시를 다시 계산하거나 이전 계획·T 필드를 제공해도 대체할 수 없습니다.

필수 keyword `image_manifest_digest`는 검토 중인 시작 전 보고와 독립적으로 확보한 별도의 예상
platform manifest pin입니다. container의 `Image`·`Config.Image`는 계속 프로필 configuration ID와
비교하고 `ImageManifestDescriptor.digest`는 별도 pin과 대조합니다.
[Docker Engine 명세](https://github.com/moby/moby/blob/v28.3.3/api/swagger.yaml#L1798-L1818)는
configuration·manifest digest를 구분합니다. 이 순수 API는 제공된 pin을 인증하거나 같은 신뢰하지
않는 container 보고에서 가져온 descriptor를 독립 근거로 만들지 않습니다.

정확한 HTTP 이름·label·nonce·컨테이너·이미지·명령·환경, 미시작·재시작 0회, 읽기 전용 root,
비특권 사용자, 고정 capability·security 옵션·namespace·자원과 비활성 port·device·restart·healthcheck를
요구합니다.

- A는 manifest와 선택한 평면 소스의 읽기 전용 private bind mount 두 개만 가지며 network는
  `none`, stdin은 비활성입니다.
- B는 bind/input mount가 없고 정확한 A의 network namespace만 공유합니다. TTY 없이 stdin을
  활성화하며 요청 schedule의 제한된 stdin 전달과 EOF는 후속 구현이 필요합니다.

stdin 기대값은 [Docker CLI create 설정](https://github.com/docker/cli/blob/v28.3.3/cli/command/container/opts.go)을
따릅니다. 실제 후보 이미지·설정 수용은 미완료입니다. 제공된 시작 전 설정의 일치로 소유권·직접 실행
근거·생명주기/쓰기 허가를 얻지 못합니다. 후속 phase는 생성 전 소유 의도를 기록하고 모든 현재 입력을
재검사하며 부분 실패 뒤에도 정확한 소유 guest·로컬 자식을 각각 정리해야 합니다.

## 남은 작업

실제로 검토한 이미지 수용과 현재 비공개 checkpoint·stage·프로필·client 사실을 별도 직접 A → B
host phase에 연결해야 합니다. 최초 phase 기한, 누적 setup·출력, 정확한 소유 객체 정리와 독립 정책
사례 전체를 유지합니다. 기존 프로세스 입력 상한은 새 HTTP schedule보다 작으므로 실제 전송 전에
HTTP 전용 stdin 연결과 회귀 검사를 구현해야 합니다. 이전 프로세스 계약을 묵시적으로 넓히지 않습니다.

그 뒤 직접 결과를 비공개 before/diff/apply/after/restore CLI 흐름에 연결하고 별도로 최종 원본의
승인·백업·현재 상태/편집 충돌 확인·복구를 구현합니다. 설치형 실제 전체 수용과 저장 결과 열람도
미완료입니다. 이 소스 API만으로 릴리스 조건을 완료하거나 발행하지 않습니다.
