# 저장소 포맷 검사

[문서](../INDEX.md) · [English](../../../development/FORMATTING.md) · 한국어

저장소 포맷 명령은 Prettier를 시작하기 전에 EditorConfig와 파일 탐색을 검증합니다.
이는 [#89](https://github.com/casing1/authzest/issues/89)의 개발/CI 경로에 한정한 완화이며,
Prettier 내장 의존성 교체나 입증한 AuthZest 런타임 보안 수정은 아닙니다.

## 명령

저장소에 기록된 frontend 의존성을 설치한 뒤 저장소 루트에서 실행합니다.

```bash
npm --prefix frontend ci
node --test scripts/format.test.mjs
node scripts/format.mjs markdown --check
node scripts/format.mjs markdown --write
npm --prefix frontend run format:check
npm --prefix frontend run format
```

포맷 차이를 확인하려면 `--check`, 포맷을 적용하려면 `--write`를 선택합니다. Markdown은 Git이
추적하는 파일만 탐색하므로 새 안내 문서는 최종 확인 전에 staging에 포함합니다. 기존 frontend
npm 명령 이름은 유지하며 `scripts/format.mjs frontend --check`와
`scripts/format.mjs frontend --write`를 호출합니다. frontend의 `dist`, `node_modules`,
`package-lock.json` 제외 규칙도 유지합니다. 포맷 자식 프로세스의 제한 시간은 120초입니다.

## 검토한 설정

루트 [`.editorconfig`](../../../../.editorconfig)는 계속 적용합니다. 4 KiB 이하의 일반 파일이어야
하며 `root = true`가 필수이고 중복 항목·잘못된 줄은 허용하지 않습니다. 검토한 section인
`[*]`, `[*.py]`, `[Makefile]`만 지원합니다. 속성은 `charset`, `end_of_line`,
`insert_final_newline`, `indent_style`, `indent_size`, `trim_trailing_whitespace`를 guard가 검토한
단순 값으로만 허용합니다. 일반 EditorConfig 포맷은 유지하며 임의 패턴·옵션은 지원하지 않습니다.

guard는 검사 범위 내 중첩·대소문자 별칭·심볼릭 링크 EditorConfig 파일을 거절합니다. 대상 탐색은
제한되며 Prettier를 실행하기 전에 선택한 파일을 검사합니다. 빈 객체인 명시적
[`scripts/prettier-options.json`](../../../../scripts/prettier-options.json)을 사용해 주변의 Prettier
설정과 실행 가능한 설정 탐색을 건너뛰면서 검토한 EditorConfig를 적용합니다.
wrapper는 `--ignore-path`를 명시하며 frontend 포맷에는 검증한
[`frontend/.prettierignore`](../../../../frontend/.prettierignore), Markdown 포맷에는 정확히
0바이트를 유지해야 하는 [`scripts/prettier-markdown.ignore`](../../../../scripts/prettier-markdown.ignore)를
사용합니다. 따라서 주변 `.gitignore`·`.prettierignore` 탐색이 wrapper 적용 범위를 결정하지 않으며
Prettier의 기본 vendor·버전 관리 디렉터리 제외 규칙은 계속 적용합니다.
frontend ignore 파일에는 앞뒤 공백 없는 정확한 검토 항목만 허용하며 LF·CRLF 줄바꿈, 빈 줄, `#`로 시작하는
주석을 지원합니다. 설정 패턴·옵션·
제외 규칙·ignore 탐색을 변경하려면 guard와 회귀 테스트를 함께 검토해야 합니다.

## 의존성 근거와 한계

2026-10-07 정적 검사에서 설치된 Prettier 3.9.6과 당시 최신 공식 Prettier 3.9.9 tarball 모두에
`brace-expansion` 5.0.6이 내장된 것을 확인했습니다. 별도 `brace-expansion` 5.0.12 lock 항목은
이 내장 바이트를 교체하지 않습니다. 검사는 선택한 bundle·parser·EditorConfig 경로 부분에
한정되며 전체 내장 코드 감사는 아닙니다. #89에서 추적하는 공개 권고는
[GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr),
[GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7),
[GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p)입니다.
이 경로의 실제 DoS와 AuthZest 런타임 취약점은 여전히 입증되지 않았으며 내장 의존성 후속 작업은
#89와 [#83](https://github.com/casing1/authzest/issues/83)에서 계속 추적합니다.

guard는 이 저장소 명령에만 적용합니다. 직접 Prettier 호출·editor 연동·직접 CJS/ESM 모듈 호출은
guard로 보장하지 않습니다. 제한 시간은 OS sandbox가 아닙니다. 이 경계는 설치된 toolchain과
workflow script를 신뢰하고, 사전 검사부터 Prettier가 다시 읽을 때까지 파일이 유지되며,
같은 사용자로 실행하는 악의적인 동시 작성자가 없다는 가정을 둡니다.

이 미출시 도구 변경은 릴리스를 만들거나 패키지 버전·기존 태그·alpha.3 산출물을 바꾸지 않습니다.
별도 릴리스 기준은 [릴리스 안내](../releases/RELEASING.md)를 참고하세요.
