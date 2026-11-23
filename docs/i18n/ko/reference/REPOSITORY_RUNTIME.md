# 외부 저장소 runtime 기반

[문서](../INDEX.md) · [English](../../../reference/REPOSITORY_RUNTIME.md) · 한국어

[#208](https://github.com/casing1/authzest/issues/208)은 선택한 바이트의 staging, 별도 T/A/B guest
진입 소스, schedule 기반 HTTP 기본 요소와 실행하지 않은 엄격한 runtime 선언을 구현합니다.
[외부 파일 흐름 설계](../development/REPOSITORY_FILE_WORKFLOW.md)에 따라
[S3 계약](REPOSITORY_VERIFICATION.md)과 [S2 비공개 파일 세션](REPOSITORY_FILE_SESSION.md)을
이어갑니다. 직접 관리하는 임시 파일과 가짜 import·pytest·server·socket·kernel collaborator로
검사했습니다. 이 기반을 확인하기 위해 외부 앱·테스트, 이미지 빌드, guest나 모델을 실행하지
않았습니다. 새 CLI/GUI 조작 흐름, 원본 프로젝트 쓰기, runtime 수용이나 릴리스는 없습니다.

## 현재 비공개 checkpoint와 봉인한 입력

`RepositoryFileSession`의 생성자와 일반 파일 결정은 계속 v1.0 전용입니다. 내부 runtime
checkpoint는 진행 중 결정이 없는 현재 `copied-before` 또는 `applied-after` 복사본을 읽고
검증합니다. 선택한 소스·context 바이트, 생성 테스트, evidence, journal revision과 파일 식별자를
포함합니다. 발급한 정확한 live checkpoint만 다시 확인할 수 있으며, 대기 결정·상태 전환·편집·교체,
닫힌 세션이나 과거 객체는 사용할 수 없습니다. 바뀌지 않은 checkpoint를 별도 T/A stage에서 함께
사용할 수 있습니다. 저장한 JSON은 checkpoint를 다시 열거나 실행 권한을 부여하지 않습니다.

`RepositoryInputStage(session, request, response, cases, plan, phase, role)`에는 live S2 checkpoint,
현재 S3 v1.1 요청·응답, host 전용 사례와 전체 검증 계획이 필요합니다. S2 기반 요청에서 전체
v1.1 요청을 재구성하고 응답 전체를 기존 v1.0 세션 응답과 대조합니다. 이 내부 대응 확인은 저장한
요청의 downgrade, 새 쓰기 API, 모델 작성 사실의 인증이나 사례 승인이 아닙니다.

T/A stage는 각각 새 비공개 트리를 만들고 보존합니다.

```text
stage/                         # host-private; never mounted as a directory
  record.json                  # host-only checkpoint and stage evidence
  input/
    manifest.json
    project/<selected paths>   # source and explicitly selected Python context only
    tests/test_authzest_regression.py   # T only
```

입력 파일은 mode `0444`, 입력 디렉터리는 `0555`로 봉인하며, 바깥 디렉터리는 `0700`, record는
`0600`을 유지합니다. staging과 create 계획 전후로 descriptor·경로명 식별자, 정확한 구성원,
mode·소유자·단일 링크 파일·바이트를 검사합니다. 일반적인 변경은 stage를 무효화하지만,
동일한 host 계정으로 쓰는 적대적 행위자에 대한 원자적 방어는 아닙니다. 부분 실패 시 파일과
할당·정리 사실을 보존합니다. `close()`는 열린 host descriptor를 닫으며, 증거를 삭제하거나
guest 정리를 주장하지 않습니다. Snapshot과 stopped-create 계획은 과거 관찰이며 재개 가능한
세션이나 실행 허가가 아닙니다.

## 공유 manifest와 파일별 mount

표준 라이브러리만 쓰는 `_repository_manifest.py`를 host 패키지 helper와 별도로 해시를 고정한
guest 자산으로 함께 사용합니다. Canonical manifest 바이트, 요청·인터페이스 ID, 명시적 테스트
인터페이스 전체와 소스·테스트 descriptor를 검증합니다. 선택 Python 파일은 1–5개이며 파일당
최대 16 KiB, 합계 64 KiB입니다. T 테스트는 비어 있지 않아야 하고 최대 16 KiB입니다. Manifest도
최대 16 KiB입니다. 중첩 package는 S3의 initializer·module 별칭 규칙을 유지합니다. T에는 테스트
메타데이터가 있으며 A는 `test: null`입니다.

Stopped-create 데이터는 `/input/manifest.json`, `/input/project/<selected path>`와 T 전용
`/input/tests/test_authzest_regression.py`에 개별 읽기 전용 bind를 선언합니다. 비공개 복사본 전체,
정책, 기대 정답, journal, host record나 무관한 저장소 파일은 mount하지 않습니다. 대상 import 전
guest 소스에서 정확한 mount 목록과 캡처 파일의 크기·hash를 대조합니다. Hash와 manifest ID는
데이터의 결합 정보이며 실제 runtime 출처나 동의를 증명하지 않습니다.

## 별도 guest bootstrap

관리하는 소스는 `runtime/repository/`에 있으며 기존 고정 사례 launcher와 분리합니다. 진입점은
정확한 Linux script, Python `-I -B`, UID/GID `65532`를 요구합니다. 상속한 환경·설정을 비우고 입력
검색 경로를 제거합니다. 프로젝트 import 전에 kernel을 확인하며, 선언한 읽기 전용 mount,
resource/cgroup 설정, capability 없음, no-new-privileges, seccomp, 비공개 process view와 좁게
지원하는 network 관찰을 요구합니다. 이 진단으로 검토한 이미지, 탈출 불가능한 격리나 부하 실험을
통한 제한 검증을 증명하지는 않습니다.

신뢰한 pytest/TestClient 또는 Uvicorn 의존성을 먼저 로드한 뒤 명시한 `.`/`src` 프로젝트 루트를
import 경로에 추가합니다. 캐시된 module이나 보호하는 의존성 이름과 충돌하면 거부합니다.
선언한 module과 단순 app attribute만 선택합니다. Host 대상 import, 프로젝트 setup·설치·탐색,
factory나 import 대체 경로는 추가하지 않습니다.

- T는 생성 테스트 파일 하나만 수집하며 conftest, 자동 plugin, 프로젝트 pytest 설정과 cache를
  사용하지 않습니다. 명시적인 trusted `client` fixture는 lifespan context에 진입하지 않고
  TestClient를 만들며 사용 후 닫습니다. 인증 override를 설치하지 않습니다. 출력과 exit status는
  신뢰하지 않는 보조 데이터입니다.
- A는 명시한 app을 trusted ASGI3 wrapper로 감싸 제공하여, 인자 없는 factory 탐지가 대상 코드를
  호출하지 못하게 합니다. Uvicorn은 loopback port `8765`, lifespan off, worker 하나를 고정하고
  reload·proxy header 처리·환경 파일을 사용하지 않습니다. 대상 코드가 startup marker를 위조할 수
  있으므로 marker는 힌트일 뿐입니다.

## 요청만 받는 B 관찰자

B에는 입력 mount나 소스·테스트 접근이 없습니다. 이후 host 구현은 시작 전에 attach하고 정확한
크기 제한 schedule을 stdin으로 보낸 뒤 stdin을 닫아야 합니다. Guest는 최대 16 KiB와 원래 남은
시간의 snapshot인 1–40,000 ms를 받습니다. 시간 측정은 guard·stdin 읽기보다 먼저 시작합니다.
EOF 대기는 여전히 block할 수 있으므로 guest 내부 확인으로 원래 host deadline과 정리를
대체해서는 안 됩니다.

HTTP codec은 기대 정답 없이 `127.0.0.1:8765`로 보내는 schedule GET 4–8개를 받습니다. 크기 제한
HTTP/1.1 Content-Length framing, 타입 있는 JSON·빈 body와 명시적 오류 record를 사용합니다.
Redirect를 따라가지 않으며 재연결·재전송이 없습니다. 첫 실패에서 멈추되 계획한 모든 행을
남깁니다. Stream을 닫았다는 사실은 T/A/B container 정리가 아닙니다. Capture는 미검증 데이터이며
S3로 가져왔다고 성공한 live phase, 결함 재현이나 검증된 수정이 되지 않습니다.

## 실행하지 않은 profile과 이미지 기준

`validate_runtime_profile`은 관리하는 자산·lock·recipe pin을 요구합니다.
`build_container_create_plan`은 `planned-not-executed`, 실행 권한 없음, `verified_fix: false`인
stopped-create argv·메타데이터만 반환합니다. 선언한 예산은 phase당 40초와 정리 10초이며 출력도
제한합니다. T/A는 512 MiB·CPU 하나·process 64개, B는 128 MiB·CPU 절반·process 32개를 선언합니다.
T/A는 network `none`, B는 A의 network namespace를 지정합니다. 실제 제한 적용과 정리는
이후 host가 관찰해야 합니다.

현재 create-plan 경로는 공백 없는 좁은 ASCII 부분집합만 받으며 kernel mountinfo decode도 ASCII
전용입니다. S3는 더 넓은 Unicode context 경로를 받을 수 있으므로 S3 통과가 create 계획이나
guest import 지원을 보장하지 않습니다. Bootstrap은 제공한 mount 사실의 escape된 공백을 표현할
수 있지만 create-plan 경로 범위가 넓어지는 것은 아닙니다. 의존성·import 누락이나 미지원 설정은
설치나 mount 확대 없이 실패해야 합니다.

`runtime/repository/images/`의 새 recipe·자산 manifest는 **새 소스 기준**을 정의합니다. 고정한
base·lock 입력과 별도 진입 자산을 사용하며, 이미지 ID는 없고 내용도 검증하지 않았습니다.
기존 고정 사례 이미지나 과거 수용 기록으로 이 pin을 충족할 수 없습니다. 이 기반을 위해
이미지를 빌드·검사·수용·실행하지 않았습니다.

이후 host 구현에는 현재 engine·config·image 식별자 검증, 소유할 guest 이름의 사전 기록,
stopped 설정 확인, 원래 deadline·출력 예산 적용, 직접 얻은 독립 관찰, live phase 구성과 정확한
guest 정리 확인이 필요합니다. CLI/GUI 연결, 현재 공유·실행 결정, 설치형 외부 흐름 수용과 별도로
검토할 원본 프로젝트 최종 수정은 #152/#150의 남은 작업입니다. 기존 S3 비교는 계속
`supplied-unverified`이며 이 소스로 독립 사례를 승인하거나 파일 적용을 허용하지 않습니다.
