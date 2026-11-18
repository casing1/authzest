<p align="center">
  <a href="../../../guides/RESULT_VIEWER.md">English</a> ·
  <strong>한국어</strong>
</p>

# 로컬 워크플로 결과 화면

[문서 목차](../INDEX.md) · [생성 파일 흐름](GENERATED_FILE_WORKFLOW.md)

소스 대시보드는 사용자가 직접 선택한 생성 파일 흐름 JSON과 기존 정적 라우트 목록을 표시합니다.
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

1. 이미 완료한 `codex-generate --file-workflow --json` 호출의 최종 stdout JSON을 준비합니다.
   계획·상호작용은 stderr에 출력됩니다. 별도로 해당 실행 흐름을 수행할 때는 `umask 077`을 쓰고
   stdout만 비공개 파일로 저장하세요. 기존 결과를 보려고 모델을 다시 호출할 필요는 없습니다.
2. 대시보드에서 워크플로 결과 파일을 선택합니다. 가져오기를 거부하면 이전 결과를 지웁니다.
   영어·한국어 선택은 UI 문구를 바꾸며 소스·diff·모델 텍스트는 기록한 내용대로 유지합니다.
3. 요약·단계별 결정·생성 테스트·정확한 diff·before/after 대조·실패·현재 복사본과 복구 상태를
   확인합니다. 과거 after 관찰은 현재 restored-before 파일의 상태가 아닙니다.

`codex-generated-file-workflow` 기록만 지원합니다. 새 소스 CLI 기록은 `schema_version: "1.0"`과
결합된 `source_evidence`를 포함합니다. 최상위 버전이 없는 이전 기록은 `legacy-unversioned`로
명시하며 없는 before 소스·선언은 제공하지 않습니다. 정적 스캔 JSON·등록 템플릿 결과·미리보기·
임의 JSON을 실제 생성 근거로 변환하지 않습니다.

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
