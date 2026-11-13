<p align="center">
  <a href="../../../development/GENERATED_REPAIR_GUESTS.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 guest 진입점 — 오프라인 소스

[문서 목차](../INDEX.md) · [HTTP relay](GENERATED_REPAIR_HTTP_RELAY.md) ·
[생명주기 모델](GENERATED_REPAIR_LIFECYCLE.md)

## 범위 — 2026-11-12 KST

이번 [#152](https://github.com/casing1/authzest/issues/152) 부분 단계는 관리형 standalone guest
launcher **소스**를 추가하고 가짜 의존성·소켓으로만 검사합니다. 실제 guest·앱·생성 테스트·소켓·
이미지·엔진은 시작하지 않습니다. 운영 executor와 세션은 계속 런타임 비활성이고 #152는 OPEN입니다.
실제 PoC 재현이나 수정 검증을 완료한 것이 아닙니다.

[guest 자산](../../../../runtime/generated_repair/)은 추후 검토한 이미지용이지 호스트 우회 실행이나
설치 CLI 명령이 아닙니다. runner 패키지를 불러오면 호스트 계층까지 import되므로 AuthZest 패키지를
의도적으로 import하지 않습니다. 각 이미지는 필요한 자산·의존성만 포함해야 하며 호스트 정답·소스
checkout·자격증명·기록을 넣지 않습니다. 이번에는 Dockerfile·의존성 lock·준비한 이미지·이미지 식별자·
활성 엔진 adapter가 없습니다. 격리가 없다고 호스트에서 이 파일을 실행하지 마세요.

## 고정 역할과 입력

| 역할 | 고정 진입점         | 입력 / 동작                                                                           |
| ---- | ------------------- | ------------------------------------------------------------------------------------- |
| T    | `test_launcher.py`  | `/input/app.py`와 `/input/tests/test_generated_ownership.py`만 사용, 고정 pytest 선택 |
| A    | `app_launcher.py`   | `/input/app.py:app`만 사용, `127.0.0.1:8765`의 단일 ASGI 서버                         |
| B    | `relay_launcher.py` | 관리형 요청 전용 codec, 앱·테스트 mount·정답·호출자 URL 없음                          |

추후 진입 호출은 Linux·`-I -B` 격리 Python·정확한 `/opt/authzest-guest/` 스크립트 배치·
UID/GID `65532`를 요구합니다. T/A는 추가 인자를 받지 않고 B는 1~40,000 밀리초의 표준 정수
남은 시간 하나만 받습니다. 이는 진단 조건이지 **격리·이미지 증명·실행 동의가 아닙니다**.
호스트가 정지 상태 컨테이너의 정확한 recipe·mount·namespace·자원 제약을 별도로 검사해야 합니다.

의존성 로드 전에 상속 환경을 지우고 고정된 신뢰 자산 폴더를 명시합니다(`-I`는 스크립트 폴더를
검색 경로에 남기지 않습니다). T/A는 `/input`을 앱 검색에 노출하기 전에 이미지 소유 pytest/Uvicorn을
불러옵니다. shell·모델 선택 명령은 사용하지 않습니다.

T는 pytest plugin 자동 로드·설정/addopts·환경 plugin·conftest 탐색·cache provider를 끄고 importlib
모드로 정확한 테스트 하나를 선택합니다. 종료 코드와 stdout/stderr는 **신뢰할 수 없는 보조 관찰**입니다.
종료 1만으로 소유권 assertion 재현을, 0만으로 수정 성공을 입증하지 않습니다. 보고 진위·소스 검토·
설치 인수 검증은 별도이며 새 보고 plugin·신뢰 통과 개수는 추가하지 않습니다.

A는 ASGI3·asyncio·h11·worker 하나를 고정하고 reload·proxy header·WebSocket·access log·lifespan
hook을 끕니다. health route도 추가하지 않습니다. import·시작 로그·프로세스 시작 성공은 신뢰할 수
있는 HTTP 준비 근거가 아니며 호스트가 누적 준비 시간 제한을 독립적으로 지켜야 합니다.

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

검토한 고정 이미지/의존성 lock·신뢰 로컬 엔진, 캡처 입력 staging/식별 재검사, 정지 생성 recipe 검사,
시작 전 attach 전송, 공유 출력/시간 제한, 영속 수집과 정확한 guest 정리, 세션/결정 연결과 별도 범위의
설치 before/적용/after/복구 수용이 남았습니다. 생성 테스트 출력이 before 근거·쓰기 권한을 만들지
않습니다. 전달 relay 사실이 일치해도 미검증·`verified_fix: false`이고 demo actor header는 인증이 아닙니다.

이번 단계는 새 제공자/소스 공유·실제 생성 import/수집/실행·운영 적용/복구·위험 수용·이슈 완료·
버전 변경·릴리스를 하지 않습니다.

참고: [pytest reference](https://docs.pytest.org/en/stable/reference/reference.html),
[Uvicorn settings](https://uvicorn.dev/settings/),
[Python socket API](https://docs.python.org/3.12/library/socket.html).
