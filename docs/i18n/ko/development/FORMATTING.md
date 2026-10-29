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

## 편집기와 미검토 pull request

Prettier는 개발용 포맷 도구이며 AuthZest의 접근통제 분석기가 아닙니다. 편집기의 포맷 기능이 저장소
guard를 자동 호출하지는 않습니다. 익숙하지 않은 PR은 먼저 GitHub diff나 제한 모드 편집기에서
살펴보세요. Checkout을 신뢰하거나 의존성을 설치하고 명령을 실행하기 전에 작업공간/설정, 포맷
스크립트, 의존성, workflow 변경을 검토합니다. Guard 자체도 신뢰하는 코드이지 그 코드를 변경하는
공격자로부터 격리하는 장치는 아닙니다.

VS Code용 선택형 [authzest-review.code-workspace](../../../../authzest-review.code-workspace)는
이 checkout 하나만 열고 다음 기본값을 제공합니다.

- `prettier.enable`은 `false`로, VS Code를 재시작한 뒤 Prettier 포맷을 비활성화합니다.
- `editor.formatOnSave`, `editor.formatOnPaste`, `editor.formatOnType`은 `false`입니다.
- `editor.codeActionsOnSave`의 `source.fixAll.prettier`는 `never`로, 이 프리셋에서 별도의 Prettier
  저장 시 동작을 요청하지 않습니다.

**파일 → 파일에서 작업 영역 열기(File → Open Workspace from File)**로 검토한 파일을 연 뒤 VS Code를
재시작하세요. 저장소 폴더만 여는 경우에는 이 프리셋을 적용하지 **않습니다**. 확장 설치나 실행 작업
추가, 사용자 전역 설정 수정, 무시된 `.vscode/` 파일 덮어쓰기는 하지 않습니다. 기존 폴더별·언어별
설정이 이 기본값을 덮어쓸 수 있으므로 설정 화면에서 해당 파일 언어에 적용되는 값을 확인하세요.
확신하기 어렵다면 확장 목록의 **Prettier - Code formatter**에서 **사용 안 함(작업 영역)
(Disable (Workspace))**을 선택하고 재시작 안내를 따르세요. 포맷을 작동시키려는 이유만으로
작업공간 신뢰를 허용하지 마세요.

익숙하지 않은 checkout은 검토하는 동안 [제한 모드(Restricted Mode)](https://code.visualstudio.com/docs/editing/workspaces/workspace-trust)를
유지하세요. 이 프리셋은 선택해서 사용하는 작업 흐름 보조 설정이지 sandbox나 강제 장치가 아닙니다.
다른 확장·코드 동작·편집기·수동 명령·직접 Prettier API 호출은 범위 밖입니다. 모든 확장 코드의 로딩을
막거나 개발자 컴퓨터의 실제 적용 설정을 증명하지 않습니다. 공식 [설정 우선순위](https://code.visualstudio.com/docs/configure/settings#settings-precedence),
[Prettier 활성화/재시작 설정](https://github.com/prettier/prettier-vscode#prettierenable-default-true),
[저장 시 동작](https://github.com/prettier/prettier-vscode#using-code-actions-on-save),
[작업공간 확장 비활성화](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace#disable-an-extension)를
참고하세요.

Checkout과 toolchain을 검토한 뒤 터미널에서 [명령](#명령)의 보호 명령을 사용하세요. 직접 Prettier
호출이나 **문서 서식 지정(Format Document)**으로 대체하지 않습니다. Guard가 설정을 거절하면
우회하지 말고 설정을 검토하세요. 다른 편집기에서도 이 checkout의 자동 Prettier 연동을 끄고 같은
명령을 사용하며, 편집기 간 설정 호환성을 보장하지 않습니다. 테스트는 프리셋 데이터와 npm 경로를
검사할 뿐 실제 편집기를 실행하지 않습니다. 이 변경은 Prettier의 내장 파서를 교체하거나 #89를
해결하거나 릴리스 위험을 수용하는 것이 아닙니다.

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
당시 설치된 Prettier 3.9.6과 그날 검사한 당시 공식 npm 최신 Prettier 3.9.9 모두에 `brace-expansion` 5.0.6이
내장된 것을 확인했습니다. 내려받은 3.9.9 tarball의 SHA-512 integrity와
SHA-1 `09b826918c91cd4cbc80e0cbd1d2a922ff04f233`은 registry 메타데이터와 일치했습니다.
당시의 별도 `brace-expansion` 5.0.12 lock 항목은
이 내장 바이트를 교체하지 않았습니다. 검사는 선택한 bundle·parser·EditorConfig 경로 부분에
한정되며 전체 내장 코드 감사는 아닙니다. #89에서 추적하는 공개 권고는
[GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr),
[GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7),
[GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p)입니다.
당시 검사한 시점의 legacy CLI는 `index.mjs`의 설정 해석을 불러왔고 CJS API도 같은 ESM
구현에 위임했습니다. 선택한 EditorConfig → Minimatch 경로와 재귀·재작성 parser 부분이
존재했습니다. 해당 시점에서 별도 lock override나 검사한 Prettier 3.9.9로의 갱신만으로
수정한 내장 구현을 제공하지는 않았습니다.

기록된 2026-10-08의 #89 전체 판정은 **`needs_review`**, 신뢰도는 **medium**이었습니다.
영향받는 내장 구현은 확인했지만 보호 명령 경로의 실제 DoS나 AuthZest 런타임 취약점은
입증하지 못했습니다. 당시 임의 section 패턴의 입력 경로는 Prettier 시작 전에 거부했습니다.
실제 직접 editor/API 설정, 낮은 신뢰도의 설정 노출, 가용성 영향은 미검증이었습니다.
모든 Prettier 호출이 안전하거나 악용 가능하다는 판정은 아니었습니다.
해당 2026-10-08 정적 판단에는 공격·자원 고갈 입력이나 동적 재현을 실행하지 않았습니다.
내장 의존성 후속 작업은 #89와 [#83](https://github.com/casing1/authzest/issues/83)에서 계속 추적합니다.
2026-10-16 문서 동기화로 업스트림 릴리스 확인·새 보안 판단·위험 수용 결정을 추가하지
않습니다. 위의 근거는 2026-10-08의 과거 기록으로 유지합니다.

guard는 이 저장소 명령에만 적용합니다. 직접 Prettier 호출·editor 연동·직접 CJS/ESM 모듈 호출은
guard로 보장하지 않습니다. 제한 시간은 OS sandbox가 아닙니다. 이 경계는 설치된 toolchain과
workflow script를 신뢰하고, 사전 검사부터 Prettier가 다시 읽을 때까지 파일이 유지되며,
같은 사용자로 실행하는 악의적인 동시 작성자가 없다는 가정을 둡니다.

2026-10-08에 검사한 런타임 소스와 packaging spec은 Prettier를 호출하거나 Node toolchain을
포함 대상으로 선택하지 않았고 선택적 대시보드는 빌드된 frontend 산출물을 사용했습니다.
이 기록은 확인한 개발 도구 경로를 런타임 주장과 구분했으며 전체 의존성 감사나 새 바이너리
내용 증명은 아니었습니다.

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
