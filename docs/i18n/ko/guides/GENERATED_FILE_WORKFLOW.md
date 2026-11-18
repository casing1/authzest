<p align="center">
  <a href="../../../guides/GENERATED_FILE_WORKFLOW.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 파일 흐름

[문서 목차](../INDEX.md) · [생성 계약](../development/GENERATED_REPAIR_CONTRACT.md) ·
[세션 계약](../development/GENERATED_REPAIR_SESSION.md)

## 현재 소스 상태 — 2026-11-15 KST

소스 CLI는 현재 생성 제안 하나를 별도 결정하는 비공개 복사본 검사·정확한 소스 적용·복구에 연결합니다.
기본 생성 명령은 제안 전용입니다. Opt-in 구현은 오프라인/mock 검사를 받았으며 현재 이미지·커널의
실현 가능성과 설치형 전체 흐름 수용은 [#152](https://github.com/casing1/authzest/issues/152)에 남아 있습니다.
불변의 공개 alpha.4 릴리스에는 포함하지 않으며 #150/#153도 미완료입니다.

범위는 관리하는 합성 소유권 사례 하나, 앱 파일 하나와 생성 테스트 하나입니다. 임의 저장소 실행기,
host pytest 우회, 브라우저 승인 흐름이나 범용 수정 엔진이 아닙니다.

## 오프라인 입력 검토

파일 흐름은 POSIX non-frozen 소스 설치와 기존 비공개 runtime profile을 요구합니다.
이미지 자동 build/pull·profile 생성기·기본 준비 완료 profile은 없습니다. 파일은 현재 사용자 소유의
일반 파일, mode `0600`, 단일 link, no-follow, 최대16 KiB 조건이어야 합니다. Loader는 현재 바이트/inode/
부모와 관리하는 platform recipe·의존성 lock·guest 자산 pin을 결합하며 잘못된 입력은 계정 사용 전에 중단합니다.

Docker 설정은 빌드용과 runtime 전용을 분리하세요. Runtime 설정은 현재 사용자 소유의 `0700` 폴더에
단일 링크·소유자 `0600`인 `config.json` 하나만 두고 정확한 바이트 `{}\n`으로 준비합니다.
[BuildKit](https://github.com/moby/buildkit/blob/master/session/auth/authprovider/tokenseed.go)은 빈 설정에서도
`.token_seed`와 `.token_seed.lock`을 만들 수 있으며 추가 항목은 `private-empty-config-required`로
거부됩니다. 사용한 빌드 폴더는 보존하고 새 runtime 폴더를 준비하세요. 기존 파일을 삭제하거나 검사를
완화하지 않습니다. 설정 경로가 바뀌면 새 profile 식별자와 새 로컬 runtime 검토가 필요하며 종료한
호출을 재개하지 않습니다.

다음은 profile 경로가 placeholder인 오프라인 예제입니다. 실제 client와 불변 이미지를 검토한
profile 경로로만 바꾸세요.

```bash
authzest codex-generate --model EXPLICIT_MODEL \
  --file-workflow --runtime-profile /absolute/private/runtime-profile.json \
  --preview-only --json
```

`sharing_preview`와 `runtime_review_preview`를 포함한 JSON 하나를 반환하며 질문·공유·복사를 하지 않습니다.
Runtime profile은 로컬 전용으로 제공자 요청에 포함하지 않습니다. 기본
`authzest codex-generate --model EXPLICIT_MODEL --preview-only`는 플랫폼 독립 공유 미리보기를 유지합니다.

## 활성 경로의 개별 결정

미리보기가 아닌 옵션에는 실제 효과가 있으므로 먼저 현재 재빌드/검토한 T/A/B 이미지와 해당 운영 검토가
필요합니다. 가져온 profile이나 입력한 확인 문구는 이미지 내용·커널 강제·OS sandbox 증거가 아닙니다.

CLI는 전체 로컬 runtime 검토와 새 invocation/profile 결합 문구를 먼저 표시합니다. 거절하면 AI 전에
중단합니다. 승인 뒤 기존 전체 소스 공유 미리보기에도 별도 정확한 현재 문구가 필요하며 adapter 시도
한 번을 허용합니다. 타당한 no-change/unknown은 복사본을 만들지 않습니다. 현재 proposed change만
다음 독립 계획으로 진행합니다.

| 단계           | 허용 효과                                                  |
| -------------- | ---------------------------------------------------------- |
| `copy`         | 새 비공개 before 앱·생성 테스트·보존 snapshot/journal 생성 |
| `before`       | T 뒤 새 A/B를 실행하고 전체 관리 before 관찰 비교          |
| `source-diff`  | 현재 정확한 앱 소스 diff 수용                              |
| `source-apply` | 해당 비공개 복사본의 검토한 `app.py` 바이트만 교체         |
| `after`        | 새로 캡처한 after 입력을 T와 독립 A/B로 검사               |
| `restore`      | 테스트·근거를 보존하면서 정확한 원래 before 바이트 복구    |

전체 계획은 현재 파일 식별자·소스/테스트/diff·profile·이전 결과를 포함합니다. 문구는 단계·세션 nonce·
계획 ID에 결합됩니다. 각 결정은 일회성이며 최초 최대 300초 만료를 대기·재준비로 연장하지 않습니다.
Enter는 거절하고 cancel은 해당 선택을 취소합니다. EOF/Ctrl-C/SystemExit는 모든 추가 질문을 중단하며
이미 기록한 효과는 계속 표시합니다. 로컬 단계 거절·실패 후에도 적용 파일·정리를 확인한 경우에만
별도 복구를 제안할 수 있습니다. 자동 복구나 발견한 편집 덮어쓰기는 없습니다.

## 결과 해석

사람용 출력은 단계·T 종료·독립 사례/요청 수·적용·복구를 요약합니다. `--details`는 전체 metadata를
포함하고 `--json`은 stdout에 최종 JSON 하나만 출력하며 현재 계획·상호작용은 stderr로 보냅니다.
원본 출력은 비공개 phase 기록에 보존합니다.

[로컬 결과 화면](RESULT_VIEWER.md)은 모델을 다시 호출하지 않고 선택한 최종 JSON을 표시합니다.
기록을 가져와도 단계를 실행하거나 변경을 적용하거나 결정을 재사용하지 않습니다.

T의 before 종료1·after 종료0은 보조 관찰이며 assertion 진위의 증명이 아닙니다. 호스트는 전체 17사례/
21요청 HTTP 결과와 정확한 입력 결합을 독립 검사합니다. 현재 직접 반환한 phase만 세션 before 근거가
되며 저장한 JSON으로 재개하지 않습니다. 복구 후 과거 after 비교는 과거 기록일 뿐 복구된 before의
통과가 아닙니다. 인가는 unknown이고 `verified_fix: false`입니다. 쓰기가 불확실하면 false/무효과로
추정하지 않고 `applied: null`과 명시적 `current_copy_state`를 표시합니다. 확인된 복구 뒤에도
과거 적용 기록은 true로 남을 수 있습니다.

## 런타임과 남은 수용

유지 관리하는 이미지 진입점은 target/tool import 전에 지원하는 커널 보고 제어를 확인합니다.
PID 1/nonroot·seccomp/no-new-privileges/zero capabilities·cgroupv2 CPU/메모리/swap/PID 제한,
읽기 전용 root/input·제한 tmpfs·닫힌 network-interface 계약을 검사합니다. 엄격한 lo-only 경로를
유지하고 두 번째 경로는 이름·type·flag가 소스의 고정 허용 목록과 정확히 같은 기본 tunnel fallback만
허용합니다. 각 non-loopback interface는 관리상 DOWN·operstate DOWN·iflink0이어야 하며 index는
양수이고 서로 달라야 합니다. 고정 proc/sysfs 경로의 제한된 전후 snapshot도 같아야 합니다.
미확인·활성·변경·잘못된 사실은 target import 전에 종료 78로 거부합니다.

네트워크 관찰의 범위는 **진입 시 활성 non-loopback interface가 관찰되지 않음**뿐입니다. IP 주소나
모든 route의 부재, 실제 외부 연결성 측정, 독립 namespace 신원·격리 증명을 뜻하지 않습니다.
socket/netlink 채널을 열지 않고 NET_ADMIN·sysctl·network template도 바꾸지 않습니다.
호스트의 단계/수집/정리 제한과 정확한 객체 소유권 확인도 유지합니다.

이번 네트워크 수정은 T/A/B 이미지가 함께 사용하는 공통 자산과 platform recipe6개의 pin을 바꾸므로
현재 재빌드/검토 이미지가 필요합니다. 이전 profile에 새 선언 해시를 넣어도 이미지가 바뀌지 않습니다. 공유 제한은 phase40초·
누적 준비10초·정리10초·출력256KiB(일반224KiB와 정리32KiB)·복구 기록 공간을 예약한 세션 근거2MiB입니다.
동기 파일시스템·커널 호출의 보편적 시간 상한은 없습니다.

이번 소스 변경에서 실제 AI/Docker/생성 실행·새 이미지 준비·운영 패치·릴리스는 수행하지 않습니다.
다음은 현재 이미지로 정확한 설치 흐름을 검증하고
[#153](https://github.com/casing1/authzest/issues/153)의 읽기 전용 로컬 결과 UI에 연결하는 작업입니다.
