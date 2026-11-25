# 외부 FastAPI 소유권 결함 수정

[문서](../INDEX.md) · [English](../../../guides/REPOSITORY_HTTP_FIX.md) · 한국어

`authzest repo-fix`는 다른 로컬 폴더에 있는 자체 완결 FastAPI 소스 파일 하나를 위한 0.1.0 CLI
흐름입니다. Codex에 GET PoC와 한 파일 수정을 요청하고, 정확한 수정 전·후 소스를 격리 A/B 컨테이너에서
직접 검토한 사례와 비교합니다. 두 검사가 모두 통과한 뒤에만 원본 파일 쓰기를 제안하며 비공개 백업을
남깁니다. 이후 파일을 편집하지 않았다면 `authzest repo-restore`로 되돌릴 수 있습니다.
[확정 범위](../development/0.1.0-SCOPE.md)를 참고하세요.

지원 환경은 macOS arm64, Python 3.12 소스 설치, 검토한 A/B 이미지가 있는 Docker Desktop입니다. 평면
`.py` 앱 파일 하나, 메모리 데이터, GET 경로, 명시 정책, 합성 사용자 헤더(`x-user`, `x-user-id`,
`x-role`)만 다룹니다. 패키지·데이터베이스·다른 HTTP 메서드·실제 로그인 체계는 지원하지 않습니다.

## 1. 입력과 사례 basis 미리보기

```bash
authzest repo-fix /path/to/project --source app.py --policy policy.md --model EXPLICIT_MODEL --preview-only --json
```

두 파일만 읽습니다. 공유될 정확한 요청과 사례 파일에 그대로 옮길 `case_basis`를 보여 줍니다. 두 파일 중
하나라도 바뀌면 basis도 바뀝니다.

## 2. 검토한 사례 파일 작성

사례 파일에는 기대 응답이 들어 있습니다. 호스트에만 남고 모델이나 컨테이너로 보내지 않습니다. GET 사례
4–8개와 지정 회귀 사례 하나를 두고 소유자 접근, 비소유자 거부, 일반 사용, 해당하면 익명 거부와 공개
경로를 포함합니다.

```json
{
  "schema_version": "2.0",
  "kind": "repository-http-independent-cases",
  "basis": { "...": "copy case_basis from step 1" },
  "authorship": "Reviewed by <name> on <date>.",
  "assumptions": ["x-user carries a synthetic test identity."],
  "regression_case_id": "other",
  "regression_reason": "A non-owner must not read another user's note.",
  "coverage": {
    "owner": { "case_ids": ["owner"], "not_applicable_reason": null },
    "non-owner": { "case_ids": ["other"], "not_applicable_reason": null },
    "anonymous": { "case_ids": ["anonymous"], "not_applicable_reason": null },
    "normal-use": { "case_ids": ["normal"], "not_applicable_reason": null },
    "public": { "case_ids": [], "not_applicable_reason": "No public route." }
  },
  "cases": [
    {
      "id": "other",
      "request": {
        "method": "GET",
        "path": "/notes/1",
        "headers": { "x-user": "test-bob" }
      },
      "before": {
        "status": 200,
        "body": { "kind": "json", "value": { "id": 1 } }
      },
      "after": {
        "status": 403,
        "body": { "kind": "json", "value": { "detail": "Forbidden" } }
      }
    }
  ]
}
```

`before`는 현재 코드가 돌려주는 응답이고 `after`는 정책이 요구하는 응답입니다. 모델 PoC는 지정 회귀
요청과 정확히 같아야 하므로 정책 문서에 합성 사용자와 객체 ID를 적어 두세요. 사례 파일은 검토 기록이며
인증된 승인이 아닙니다.

## 3. 흐름 실행

```bash
authzest repo-fix /path/to/project --source app.py --policy policy.md --model EXPLICIT_MODEL --cases cases.json --runtime-profile ~/.authzest/runtime.json
```

효과마다 300초 동안 유효한 확인 코드를 따로 입력해야 하며 Enter는 거절하고 멈춥니다.

1. **share** – 미리 본 소스와 정책을 Codex에 보내 제안 하나를 받습니다.
2. **copy** – 새 비공개 복사본을 만듭니다. 원본은 그대로입니다.
3. **run-before** – 비공개 수정 전 소스를 A에서 실행하고 B에서 관찰해 `before` 응답과 비교합니다. 지정
   회귀가 재현되지 않으면 멈춥니다.
4. **apply-private** – 정확한 diff를 승인하고 비공개 복사본에만 적용합니다.
5. **run-after** – 수정한 복사본을 모든 `after` 응답과 비교합니다.
6. **apply-original** – 원본과 정책이 캡처 이후 그대로인지 다시 확인하고 백업을 남긴 뒤 수정을 씁니다.
   캡처 이후 편집이 있으면 충돌로 거절합니다. 교체 파일은 권한·그룹·ACL·확장 속성을 그대로 유지합니다.
   다른 사용자 소유 파일, 파일 플래그가 있는 파일, 메타데이터를 정확히 재현할 수 없는 파일은 거절하고
   원본을 그대로 둡니다.

`--json`은 최종 `repository-http-fix-result` 하나를 출력하며 진행 상황은 stderr로 나갑니다. 각 검사는
journal과 전체 결과가 담긴 비공개 근거 디렉터리를 남깁니다. 최종 JSON을 저장하면(예: `umask 077`)
[결과 뷰어](RESULT_VIEWER.md)에서 읽기 전용으로 열 수 있습니다.

## 결과

| 상태                                                 | 의미                                                 |
| ---------------------------------------------------- | ---------------------------------------------------- |
| `original-applied`                                   | 두 검사가 일치했고 원본에 수정이 적용되었습니다.     |
| `original-declined`                                  | 두 검사가 일치했고 원본은 그대로 두었습니다.         |
| `before-not-reproduced`                              | 수정 전 소스에서 검토한 결함이 나타나지 않았습니다.  |
| `after-not-verified`                                 | 수정한 복사본이 일부 검토 사례와 맞지 않았습니다.    |
| `poc-not-covered`                                    | 모델 PoC가 지정 회귀 요청과 다릅니다.                |
| `original-conflict`                                  | 캡처 이후 원본이나 정책이 바뀌어 쓰지 않았습니다.    |
| `*-phase-failed`, `original-recovery-required`, 기타 | 단계가 실패했습니다. `failure`와 보존 근거를 보세요. |

`verified_fix: true`는 after 검사가 **직접 검토한 사례**와 일치했다는 뜻입니다. 앱 전체, 실제 인증
체계, 그 요청 밖의 동작을 보증하지 않습니다.

## 원본 복구

```bash
authzest repo-restore ~/.authzest/recovery/original-YYYYMMDDTHHMMSSZ-xxxxxxxx
```

기록과 파일의 현재 상태를 보여 준 뒤 확인 코드를 묻습니다. 파일이 적용한 수정과 정확히 같을 때만 백업을
되돌리고, 이후 편집이 있으면 거절해 그 편집을 남깁니다. 기록 디렉터리에는 `before.py`, `after.py`,
`record.json`이 남습니다.
