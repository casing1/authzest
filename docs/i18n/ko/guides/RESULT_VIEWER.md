<p align="center">
  <a href="../../../guides/RESULT_VIEWER.md">English</a> ·
  <strong>한국어</strong>
</p>

# 로컬 워크플로 결과 화면

[문서 목차](../INDEX.md) · [생성 파일 흐름](GENERATED_FILE_WORKFLOW.md)

소스 대시보드는 사용자가 직접 선택한 소유자 조회 또는 생성 파일 흐름 JSON과 기존 정적 라우트
목록을 표시합니다.
로컬에서 실행하므로 웹사이트 배포가 필요하지 않습니다. 공유·결정·생성 코드 실행·수정 적용·복구는
계속 CLI에서 수행합니다.

## 지원하는 소스 설치

Python 3.12와 npm을 준비한 뒤 소스 checkout에서 실행합니다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
cd frontend
npm ci
npm run build
cd ..
.venv/bin/authzest ui --workspace .
```

`http://127.0.0.1:8000`을 엽니다. 서버를 유지하고 Ctrl-C로 종료합니다.
`authzest ui --help`에서 `--host`, `--port`, `--reload`, `--workspace`를 확인할 수 있습니다.
Workspace는 정적 스캔 대상을 고정하며 결과 폴더를 지정하는 옵션이 아닙니다. UI 소스를 바꾸면
frontend를 다시 빌드합니다. API가 `frontend/dist`를 찾도록 editable 소스 설치를 사용하는 경로입니다.
Wheel과 native 스캔·미리보기 바이너리를 완전한 활성 흐름·UI 설치본으로 안내하지 않습니다.

## 기존 결과 가져오기

1. 이미 검토하고 실행한 `owner-read-suggest --file-workflow --runtime-config … --json` 호출의
   최종 stdout JSON을 준비합니다. 계획·상호작용은 stderr에 출력됩니다. `umask 077`로 비공개
   파일에 stdout을 저장합니다. 런타임 준비와 공유·복사본·before·diff·적용·after·복구 결정은
   흐름 계약에서 설명합니다. [소유자 조회 흐름 계약](../development/GENERATED_REPAIR_CONTRACT.md#승인형-복사본-흐름-실행)
2. 대시보드에서 해당 결과 파일을 선택합니다. 가져오기를 거부하면 이전 결과를 지웁니다.
   영어·한국어 선택은 UI 문구를 바꾸며 소스·diff·모델 텍스트는 기록한 내용대로 유지합니다.
3. 요약·단계별 결정·소스·생성 회귀 테스트·정확한 diff·before/after 대조와 복구 필요 상태를
   확인합니다. after 열은 복구 전에 검사한 복사본의 관찰 결과입니다.

저장한 결과를 열 때는 선택한 바이트를 사용하며 모델을 다시 호출할 필요가 없습니다. 현재 소유자 조회
결과는 `kind: "owner-read-suggestion"`, `schema_version: "1.0"`을 사용합니다. 제안만 있는 기록,
거절과 불완전한 기록도 확보된 관찰값과 함께 표시합니다. 선택한 기록에 포함된 경우 before 소스와
정책을 표시합니다. 소스 근거가 없는 이전 소유자 조회 기록은 자료 없음 경고를 표시합니다.

관리하는 보관 노트 사례의 기대 화면은 다음과 같습니다.

| 단계   | 소유자의 보관 노트 | pytest 회귀 테스트     | 의도한 정책 일치 |
| ------ | ------------------ | ---------------------- | ---------------- |
| Before | HTTP 403           | 단언 실패, 종료 코드 1 | 6/7              |
| After  | HTTP 200           | 통과, 종료 코드 0      | 7/7              |

별도의 기대 프로필 일치 개수는 두 단계 모두 7/7일 수 있습니다. before는 관찰한 결함 baseline을
그 단계의 기대 baseline 응답과 비교합니다. 의도한 정책 일치는 관찰 7개 중 목표 정책을 만족하는
개수를 보여 줍니다. 이 수치와 함께 복구 및 복구 필요 상태도 확인합니다. 복구된 복사본은 원래 소스
바이트를 포함합니다. 앞선 after 관찰이 통과했어도 복구가 필요하면 해당 상태를 계속 표시합니다.

이전 `codex-generated-file-workflow` 가져오기도 지원합니다. 버전 1.0 기록에는 결합된
`source_evidence`가 포함됩니다. 최상위 버전이 없는 이전 기록은 `legacy-unversioned`로 표시하고
없는 before 소스·선언은 자료 없음으로 유지합니다. 정적 스캔 JSON·등록 템플릿 결과·미리보기·임의
JSON은 각각 별도 형식이며 이 워크플로 가져오기에서 거절합니다.

## 가져오기 경계와 해석

파일 선택은 선택한 바이트를 로컬 API의 `POST /api/results/preview`로 전송합니다. 브라우저와 API는
파일을 **512 KiB**로 제한합니다. API는 제한된 JSON 형식과 지원 버전을 검사한 뒤 스키마 `1.0`,
provenance `imported-unverified`의 `authzest-workflow-view` 표시 자료를 반환합니다. 파일시스템
경로를 받거나 가져온 기록을 저장하지 않으며 receipt 폴더 조회·명령 실행·모델 호출·패치 적용도
하지 않습니다. 비공개 기록을 호스팅된 viewer에 올리지 마세요.

소스·테스트·diff·설명은 신뢰하지 않는 텍스트로 취급하며 HTML·Markdown 실행 없이 표시합니다.
표시 자료는 로컬 workspace/근거 경로·runtime profile·계정/사용량 metadata·실행 ID를 제외합니다.
이는 범용 비밀정보 제거 도구가 아닙니다. 선택한 소스나 모델 텍스트 자체에도 민감한 정보가 있을 수
있습니다. 원본 JSON과 phase 원본 캡처는 기존 비공개 위치에 남으며 화면이 조회하거나 인증하지 않습니다.

가져오기는 기록에 적힌 주장을 보여 줍니다. 완료·승인한 결정·테스트 종료값·유한 대조 일치는 보안
통과나 새 권한, 인증된 실행 증거가 아닙니다. 불명·미실행·거절·미지원·실패·복구 필요 상태를
구별합니다. Before/after 개수는 관리하는 유한 대조를 뜻하며 생성 테스트 보고는 보조 자료입니다.
화면은 실제 인증·자원 강제·격리·범용 수정 검증을 확립하지 않습니다. 기록을 열어도 세션을 재개하거나
승인을 재사용할 수 없습니다.
