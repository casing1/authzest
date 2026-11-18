<p align="center">
  <a href="../../../development/GENERATED_REPAIR_GUESTS.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 guest 진입점 — 오프라인 소스

[문서 목차](../INDEX.md) · [HTTP relay](GENERATED_REPAIR_HTTP_RELAY.md) ·
[생명주기 모델](GENERATED_REPAIR_LIFECYCLE.md)

## 범위 — 2026-11-18 KST

이번 [#152](https://github.com/casing1/authzest/issues/152) 부분 단계는 관리형 standalone guest
launcher **소스**를 추가하고 가짜 의존성·소켓으로만 검사합니다. 실제 guest·앱·생성 테스트·소켓·
이미지·엔진은 시작하지 않습니다. 명시적 [CLI 파일 흐름](../guides/GENERATED_FILE_WORKFLOW.md)은
현재 세션 결정을 phase 실행기에 연결하고 기본 생성은 제안 전용을 유지합니다. 현재 이미지의 설치형
수용은 남아 있고 #152는 OPEN이며 소스 테스트로 실제 PoC 재현·수정 검증을 완료하지 않습니다.

[guest 자산](../../../../runtime/generated_repair/)은 추후 검토한 이미지용이지 호스트 우회 실행이나
설치 CLI 명령이 아닙니다. runner 패키지를 불러오면 호스트 계층까지 import되므로 AuthZest 패키지를
의도적으로 import하지 않습니다. 각 이미지는 필요한 자산·의존성만 포함해야 하며 호스트 정답·소스
checkout·자격증명·기록을 넣지 않습니다. 이후 [고정 이미지 입력](GENERATED_REPAIR_IMAGES.md)은
Dockerfile·의존성 lock을 추가하고 [비공개 단계 실행기](GENERATED_REPAIR_PHASE.md)는 fake만으로
내부 전송을 연결합니다. 소스 opt-in 흐름에는 현재 재빌드/검토 이미지가 필요하며 이 문서가
실제 런타임 수용을 입증하지 않습니다. 격리가 없다고 호스트에서 이 파일을 실행하지 마세요.

## 고정 역할과 입력

| 역할 | 고정 진입점         | 입력 / 동작                                                                           |
| ---- | ------------------- | ------------------------------------------------------------------------------------- |
| T    | `test_launcher.py`  | `/input/app.py`와 `/input/tests/test_generated_ownership.py`만 사용, 고정 pytest 선택 |
| A    | `app_launcher.py`   | `/input/app.py:app`만 사용, `127.0.0.1:8765`의 단일 ASGI 서버                         |
| B    | `relay_launcher.py` | 관리형 요청 전용 codec, 앱·테스트 mount·정답·호출자 URL 없음                          |

진입 호출은 Linux·`-I -B` 격리 Python·정확한 `/opt/authzest-guest/` 스크립트 배치·
UID/GID `65532`를 요구합니다. T/A는 추가 인자를 받지 않고 B는 1~40,000 밀리초의 표준 정수
남은 시간 하나만 받습니다. 이는 진단 조건이지 **격리·이미지 증명·실행 동의가 아닙니다**.
호스트가 정지 상태 컨테이너의 정확한 recipe·mount·namespace·자원 제약을 별도로 검사해야 합니다.

공통 guard는 target/tool import 전에 고정 커널 경로를 읽어 미지원 PID/nonroot·seccomp/
no-new-privileges/capability·cgroup·mount·interface 설정을 종료 78로 거부합니다. 대상 내용은
읽지 않고 프로세스·소켓도 만들지 않습니다. 좁은 지원 속성 검사이지 자원 부하 벤치마크·탈출 불가·
독립 A/B namespace 증명이 아닙니다.

네트워크 guard는 엄격한 lo-only 수용을 유지하고 닫힌 기본 tunnel fallback 경로를 추가합니다.
이름·type·flag가 관리하는 소스 상수와 같아야 하며 모든 non-loopback fallback은 관리상 DOWN·
operstate DOWN·iflink0, 양수이며 서로 다른 index 조건을 만족해야 합니다. 고정 proc/sysfs snapshot을
제한해 전후 비교하고 미확인·활성·변경·잘못된 데이터는 target import 전에 종료 78로 거부합니다.
관찰은 **진입 시 활성 non-loopback interface가 관찰되지 않음**뿐이며 주소/모든 route의 부재·
실제 외부 연결성 측정·격리 증명이 아닙니다. socket/netlink·NET_ADMIN·sysctl·network template 변경은 없습니다.

이번 공통 자산 변경으로 T/A/B의 공통 pin과 platform recipe6개가 모두 바뀌므로 현재 이미지로
재빌드·검토해야 합니다. 입력한 runtime 검토나 갱신한 선언은 이미지 내용의 대체가 아닙니다.

의존성 로드 전에 상속 환경을 지우고 고정된 신뢰 자산 폴더를 명시합니다(`-I`는 스크립트 폴더를
검색 경로에 남기지 않습니다). T/A는 `/input`을 앱 검색에 노출하기 전에 이미지 소유 pytest/Uvicorn을
불러옵니다. shell·모델 선택 명령은 사용하지 않습니다.

T는 pytest plugin 자동 로드·설정/addopts·환경 plugin·conftest 탐색·cache provider를 끄고 importlib
모드로 정확한 테스트 하나를 선택합니다. 종료 코드와 stdout/stderr는 **신뢰할 수 없는 보조 관찰**입니다.
종료 1만으로 소유권 assertion 재현을, 0만으로 수정 성공을 입증하지 않습니다. 보고 진위·소스 검토·
설치 인수 검증은 별도이며 새 보고 plugin·신뢰 통과 개수는 추가하지 않습니다.

A는 ASGI3·asyncio·h11·worker 하나를 고정하고 reload·proxy header·WebSocket·access log·lifespan
hook을 끕니다. health route도 추가하지 않습니다. import·시작 로그·프로세스 시작 성공은 신뢰할 수
있는 HTTP 준비 근거가 아닙니다. 유지 관리하는 startup은 서버 시작 뒤에만 `AUTHZEST_A_STARTED`를
출력하지만 앱이 stdout 신호를 위조할 수 있습니다. 비공개 조정기는 누적 준비 시간을 지키며 B의 순서
조정에만 이를 사용하고, 완전한 독립 HTTP 관찰을 별도로 요구합니다.

B는 숫자 IPv4 loopback과 요청마다 새로운 TCP 소켓만 쓰며 hostname 탐색·proxy·`create_connection`을
사용하지 않습니다. 연결 dispatch 전에 codec이 소켓 소유권을 받아 연결/설정 실패·취소에도 닫기를
시도합니다. 재연결·요청 재시도는 없고 제한된 완전/부분 JSON을 호스트에 전달합니다. 대상 로그는
relay 사실이 아니고 소켓 닫기는 guest 종료/제거 확인이 아닙니다.

## 시계 기준은 분리하고 호스트 원래 마감을 유지

Mac 호스트와 Linux guest의 monotonic 기준은 같다고 가정할 수 없습니다. 호스트 절대 시각 숫자를
guest에 그대로 전달하지 않습니다. 추후 호스트는 T와 A/B 준비·수집을 포함한 원래 40초 phase 마감과
그 안의 누적 준비 10초를 유지합니다. B는 **남은 시간 길이**의 snapshot만 받아 guest 내부 절대
마감 하나로 바꾸며 연결·요청·chunk마다 갱신하지 않습니다.

guest timer는 협조적 보조 제한이지 호스트 원래 마감의 대체·연장이 아닙니다. 시작/전송 지연으로
호스트 시간을 늘려서는 안 됩니다. 호스트는 guest 시계·출력과 무관하게 원래 제한에 따라 종료하고
정리를 확인해야 합니다. callback·파일시스템·daemon·kernel의 보편적인 강제 시간 상한은 아닙니다.

## 남은 운영 연결

Staging·정지 생성 inspect·attach/수집/정리·세션/CLI 결정을 구현하고 fake/비활성 파일로 검사합니다.
현재 재빌드 이미지 내용·커널 실현 가능성과 별도 범위의 설치형 before/적용/after/복구 수용은 남아 있습니다.
생성 테스트 출력만으로 before 근거·쓰기 권한을 만들지 않으며 호스트는 완전한 현재 독립 관찰과
정리 확인을 요구합니다. 내보낸 데이터는 `verified_fix: false`를 유지하고 demo actor header는 인증이 아닙니다.

이번 단계는 새 제공자/소스 공유·실제 생성 import/수집/실행·운영 적용/복구·위험 수용·이슈 완료·
버전 변경·릴리스를 하지 않습니다.

참고: [pytest reference](https://docs.pytest.org/en/stable/reference/reference.html),
[Uvicorn settings](https://uvicorn.dev/settings/),
[Python socket API](https://docs.python.org/3.12/library/socket.html).
