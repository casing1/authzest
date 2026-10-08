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

소스 커밋 `4218b807ad892bb92e27a6bb23c4d64000e2a3bf` 기준으로 2026-10-08 정적 재검사를 했습니다.
설치된 Prettier 3.9.6과 현재 공식 npm 최신 Prettier 3.9.9 모두에 `brace-expansion` 5.0.6이
내장된 것을 확인했습니다. 내려받은 3.9.9 tarball의 SHA-512 integrity와
SHA-1 `09b826918c91cd4cbc80e0cbd1d2a922ff04f233`은 registry 메타데이터와 일치했습니다.
별도 `brace-expansion` 5.0.12 lock 항목은
이 내장 바이트를 교체하지 않습니다. 검사는 선택한 bundle·parser·EditorConfig 경로 부분에
한정되며 전체 내장 코드 감사는 아닙니다. #89에서 추적하는 공개 권고는
[GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr),
[GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7),
[GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p)입니다.
legacy CLI는 `index.mjs`의 설정 해석을 불러오고 CJS API도 같은 ESM 구현에 위임합니다.
선택한 EditorConfig → Minimatch 경로와 재귀·재작성 parser 부분은 여전히 남아 있습니다.
lock override나 이번에 검사한 최신 버전으로의 갱신만으로는 권고에서 수정한 내장 구현으로
교체되지 않습니다.

#89 전체 판정은 **`needs_review`**, 신뢰도는 **medium**입니다. 영향받는 내장 구현은 확인했지만,
보호 명령 경로의 실제 DoS나 AuthZest 런타임 취약점은 입증하지 못했습니다. 임의 section 패턴의
입력 경로는 Prettier 시작 전에 거부합니다. 실제 직접 editor/API 설정, 낮은 신뢰도의 설정 노출,
가용성 영향은 미검증입니다. 모든 Prettier 호출이 안전하거나 악용 가능하다는 판정은 아닙니다.
이번 정적 판단에는 공격·자원 고갈 입력이나 동적 재현을 실행하지 않았습니다.
내장 의존성 후속 작업은 #89와 [#83](https://github.com/casing1/authzest/issues/83)에서 계속 추적합니다.

guard는 이 저장소 명령에만 적용합니다. 직접 Prettier 호출·editor 연동·직접 CJS/ESM 모듈 호출은
guard로 보장하지 않습니다. 제한 시간은 OS sandbox가 아닙니다. 이 경계는 설치된 toolchain과
workflow script를 신뢰하고, 사전 검사부터 Prettier가 다시 읽을 때까지 파일이 유지되며,
같은 사용자로 실행하는 악의적인 동시 작성자가 없다는 가정을 둡니다.

검사한 런타임 소스와 packaging spec은 Prettier를 호출하거나 Node toolchain을 포함 대상으로
선택하지 않으며 선택적 대시보드는 빌드된 frontend 산출물을 사용합니다. 확인한 개발 도구 경로를
런타임 주장과 구분하는 근거이지 전체 의존성 감사나 새 바이너리 내용 증명은 아닙니다.

## 프리릴리스 판단

#89와 #83은 열어 둡니다. 일반 개발과 별도로 범위를 정한 후보 호환성·산출물 검사는 계속할 수
있지만 CI 통과나 npm 감사 0만으로 남은 내장 위험을 판단하지 않습니다. 태그 생성이나 발행 전에는
검토한 호환 업스트림 교체와 실제 배포 바이트·정상 호환성 근거를 기록하거나, 정확한 후보의 잔여
개발 도구 위험에 대한 관리자의 명시적인 결정을 기록해야 합니다. 이 결정에는 wrapper만 보호하는
범위, 보호하지 않는 연동, 가정, 남은 검증 공백과 후속 작업을 적어야 합니다. 이번 판단은
위험 수용 승인이 아닙니다. 예상값 수용과 지원한다고 안내한 플랫폼·설치 검사 등 다른 릴리스 조건도 별개로
남아 있습니다. [릴리스 안내](../releases/RELEASING.md)를 참고하세요.

이 미출시 도구 변경은 릴리스를 만들거나 패키지 버전·기존 태그·alpha.3 산출물을 바꾸지 않습니다.
별도 릴리스 기준은 [릴리스 안내](../releases/RELEASING.md)를 참고하세요.
