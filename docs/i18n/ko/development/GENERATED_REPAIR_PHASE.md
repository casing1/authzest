<p align="center">
  <a href="../../../development/GENERATED_REPAIR_PHASE.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 비공개 단계 실행기

[문서 목차](../INDEX.md) · [세션](GENERATED_REPAIR_SESSION.md) ·
[이미지 입력](GENERATED_REPAIR_IMAGES.md)

## 현재 범위 — 2026-11-15 KST

이 [#152](https://github.com/casing1/authzest/issues/152) 부분 구현은 비공개 입력 staging,
고정 Docker 명령, 동시 출력 수집, 호스트 HTTP 비교를 내부 T → 새 A/B 단계로 연결합니다.
테스트에는 비활성 파일, 가짜 자식/파이프, 가짜 Engine 응답만 사용합니다. Docker 시작이나
생성 Python import, 설치형 실제 실행 수용은 수행하지 않습니다.

기본 생성 명령과 준비 전용 세션은 그대로입니다. 명시적
[CLI 파일 흐름](../guides/GENERATED_FILE_WORKFLOW.md)이 현재 profile/파일 결합 결정과 정확한
비공개 복사본 적용·복구에 이 phase를 연결합니다. 런타임 결과 가져오기는 없습니다. 운영자는 실제
고정 client와 현재 불변 이미지 내용을 검토해야 하며 profile/inspect JSON이나 확인 문구는
이미지·커널 증명이 아닙니다.

고정 이미지 진입점은 target/tool import 전에 지원하는 커널 제어를 확인하고 미지원이면 종료 78로
거부합니다. 모든 guest 자산과 recipe 6개가 바뀌어 현재 재빌드/검토한 T/A/B 이미지가 필요합니다.
좁은 커널 보고 설정의 관찰이며 부하 벤치마크·탈출 불가 sandbox가 아닙니다. 현재 이미지 실현
가능성과 설치형 수용은 남아 있습니다.

## 고정 실행과 관찰

조정기는 실행 전에 고정 실행 파일, 비공개 빈 config, 로컬 endpoint, 현재 workspace/stage를
재검사합니다. 정지 생성 전에 새 소유 이름/nonce를 기록하고 반환된 전체 ID를 확보하며 정지 inspect를
재구성한 생성 계획과 비교합니다. 제한·mount·namespace·기본 seccomp 선택·상속 이미지 환경은
daemon이 보고한 설정일 뿐 **실제 커널 강제나 전체 이미지 검증이 아닙니다**. 지원하지 않거나 모호한
표현을 같은 의미로 간주하지 않고 실패합니다.

stdin을 닫고 non-TTY 스트림으로 신뢰한 고정 CLI의 `start --attach`를 사용합니다. CLI는 시작 전에
연결하며 조정기는 결합된 시도 하나를 기록합니다. 별도 관찰하지 않은 연결 성공을 만들어 내지 않습니다.
EOF·CLI 종료만으로 완료하지 않고 T/B의 정지 종료/OOM/오류 inspect도 대조합니다. B가 실행되는 동안
A 출력도 계속 수집합니다.

A의 유지 관리하는 Uvicorn 시작은 startup이 반환되고 started가 참일 때 `AUTHZEST_A_STARTED`를
출력합니다. 생성 앱이 stdout 표식을 위조할 수 있으므로 순서 조정 신호일 뿐입니다. B는 정확한 소유
A network namespace에서 고정 요청 21개를 재시도 없이 한 번씩 수행합니다. 호스트는 17개 사례를
의도한 before 결함 또는 after 정책과 비교합니다. T의 종료 0/1과 출력은 보조 자료이며 pytest 성공이나
시작 표식이 수정 증명·적용 권한을 만들지 않습니다.

## 공유 제한·정리·근거 보존

원래 단계 제한은 40초, 누적 준비·시작 확인은 10초입니다. 종료 정리는 남은 컨테이너와 로컬 자식 전체가
추가 10초 하나를 공유합니다. 명령이나 역할마다 단계·정리 시간을 새로 부여하지 않습니다.

생성·inspect·정리를 포함한 모든 CLI stdout/stderr는 256 KiB를 공유합니다. 일반 단계는 224 KiB에서
중단하고 정리용 32 KiB를 예약합니다. 일반 출력 실패 뒤 기존 로컬 수집 파이프를 닫아 정확한 guest
제거 시도 공간을 남기며 완전한 EOF를 관찰했다고 표시하지 않습니다. 기존 메타데이터 reader는
Engine wire 바이트를 별도로 제한합니다. 조정기의 누적 2 MiB 근거 예산에는 journal JSON과
메타데이터 wire 사용량을 계산하고, 저장 실패 시에도 base64 확장을 포함한 제한된 결과마다
512 KiB를 예약합니다. Opt-in 세션은 before/after 전체에서 같은 예산 객체를 유지하고 효과 전에
최종 요약·복구 계획 공간도 예약합니다. 수집·정리로 초기화하지 않습니다. 동기 파일시스템·프로세스 생성·daemon·커널
작업 전체에 대한 보편적인 시간 상한은 없습니다.

정확한 소유 ID를 inspect한 뒤 강제 제거합니다. 생성 결과가 불명확하면 사전 기록한 고유 이름과
일치하는 소유 label로만 대조합니다. 전체 prune, 원본 checkout mount, 호스트 실행 대체, 이미지
pull/build, 호출자 URL, 인증정보 전달은 추가하지 않습니다. 로컬 CLI 종료는 컨테이너 제거 증거가
아니며 정리 실패·미확인은 단계 실패로 남습니다.

비공개 journal, 제한된 원본 출력, 결과 기록을 보존합니다. 뒤의 정리 오류가 최초 실패를 덮지 않으며
가능한 경우 과거 결과를 첨부해 취소를 전파합니다. 내보낸 JSON은 인가 unknown,
`verified_fix: false`, 소스 미적용을 유지합니다. 가져와서 before 근거나 쓰기 권한을 만들 수 없습니다.

## 남은 수용

공통 커널 guard와 T/A/B launcher가 바뀌어 모든 guest 자산과 platform recipe 6개의 digest가
갱신됐습니다. 이전 이미지 기록은 현재 소스와 맞지 않으며 의존성 lock은 그대로입니다.
Profile 선언을 갱신해도 이미지가 재빌드·검증되지 않습니다.

Opt-in 세션/CLI 연결은 구현했습니다. 다음은 현재 이미지 실현 가능성과 별도 범위의 설치형
before/적용/after/복구 수용입니다. 동작하는 CLI 뒤에 읽기 전용 로컬 결과 UI를 연결합니다.
#152·#153·정식 릴리스는 아직 미완료입니다.

참고: [Docker CLI start 소스](https://github.com/docker/cli/blob/v29.4.3/cli/command/container/start.go),
[Uvicorn server 소스](https://github.com/Kludex/uvicorn/blob/0.54.0/uvicorn/server.py).
