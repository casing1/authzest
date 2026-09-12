<p align="center">
  <a href="../../../CONTRIBUTING.md">English</a> ·
  <strong>한국어</strong>
</p>

# AuthZest 기여 안내

AuthZest는 작고 검증 가능한 변경을 꾸준히 병합하는 방식으로 개발합니다. 기능 수보다 변경 이유,
검증 과정, 보안상 판단이 이력에 명확히 남는 것을 우선합니다.
프로젝트 안내 문서는 [문서 목차](INDEX.md)에서 찾을 수 있습니다.

## 작업 흐름

1. [roadmap issue](https://github.com/casing1/authzest/issues/1)를 확인한 뒤, 구현 전에 문제, 범위,
   완료 조건이 명확한 개별 GitHub issue를 만들거나 선택합니다.
2. 최신 `main`에서 issue 번호가 포함된 짧은 작업 브랜치를 만듭니다.
3. 한 가지 목적에 집중해 구현하고 같은 변경에서 테스트를 추가합니다.
4. 로컬 검증을 통과시킨 뒤 의미 있는 단위로 커밋합니다.
5. issue를 연결한 pull request를 열고 필수 Python, frontend, CodeQL 검사 결과를 확인합니다.
6. 대화와 CI가 정리되면 merge commit으로 병합하고 작업 브랜치를 삭제합니다.

`main`에는 직접 push하지 않으며 항상 실행 가능하고 테스트를 통과하는 상태를 유지합니다.
[브랜치 보호 정책](development/BRANCH_RULES.md)에 따라 Python, frontend, CodeQL 검사를 통과해야 합니다.

## 이슈·PR 필수 메타데이터

릴리스 준비 때만이 아니라 이슈나 pull request를 생성할 때마다 아래 규칙을 적용합니다.

- **담당자:** 현재 관리자 중심 작업 흐름에서는 `casing1`을 포함합니다. 기존 담당자를 지우지 않고
  관리자를 추가합니다. 담당자는 작업 책임자이고 작성자는 실제 생성한 계정의 기록입니다.
  작성자·봇의 출처 기록은 다시 쓰지 않고 보존합니다.
- **라벨:** `bug`, `enhancement`, `documentation`, `maintenance`에서 작업 종류에 맞는 것을 고릅니다.
  해당하는 영역인 `area:core`, `area:api`, `area:ci`, `area:release`, `area:codex`를 추가합니다.
  계획이나 여러 단계에 걸친 작업에는 `roadmap`을 사용합니다. `security`는 보안 관련 작업이지 확인된
  취약점이라는 뜻은 아닙니다. [기존 라벨](https://github.com/casing1/authzest/labels)을 재사용하고,
  이미 지정된 유효한 라벨은 보존하며 불필요하게 중복되는 분류는 만들지 않습니다.
- **마일스톤:** 관련된 열린 [마일스톤](https://github.com/casing1/authzest/milestones)을 선택하고
  한 작업의 이슈와 PR을 맞춥니다. #1 같은 전체 로드맵과 실제로 여러 마일스톤에 공통인 운영 작업은
  본문에 명시적인 이유가 있을 때만 마일스톤을 비울 수 있습니다. 필드를 채우려고 완료된 릴리스
  마일스톤을 다시 열거나 임의 마감일을 만들지 않습니다.
- **생성 확인:** 지원되면 생성 시 메타데이터를 함께 지정하고, 지원되지 않으면 생성 직후 지정합니다.
  완료했다고 알리기 전에 실제 이슈·PR을 재조회하여 라벨·담당자·마일스톤 또는 기록된 예외와 연결된
  이슈를 확인합니다. 체크리스트 문구를 복사하는 것만으로 GitHub 필드가 설정되지는 않습니다.

관리자가 반드시 지켜야 하는 작업·리뷰 규칙이며, GitHub나 CI가 메타데이터를 자동 입력하거나
강제한다는 뜻은 아닙니다. 병합 전에도 다시 확인하며 기존 필수 CI·리뷰 기준은 그대로 적용합니다.

## 브랜치 이름

형식은 `<type>/<issue-number>-<short-description>`입니다. 설명은 소문자 영문과 하이픈을
사용합니다.

```text
feat/12-router-prefix-resolution
fix/23-invalid-python-path
test/31-nested-router-fixtures
docs/7-security-model
refactor/42-report-model
chore/55-update-actions
```

권장 type은 `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`, `build`입니다. 장기간 유지하는
`develop` 브랜치는 두지 않습니다. 릴리스는 검증된 `main` 커밋에 `v0.1.0-alpha.2` 같은 태그를
붙여 만듭니다. [릴리스 안내](releases/RELEASING.md)를 따르며 공개된 태그는 변경하지 않습니다.

## 커밋 규칙

[Conventional Commits](https://www.conventionalcommits.org/)의 간단한 형태를 사용합니다.

```text
<type>(<scope>): <summary>
```

- summary는 명령형 영문으로 작성하고 마침표 없이 72자 이내로 제한합니다.
- 커밋 하나에는 되돌리거나 검토할 수 있는 한 가지 논리적 변경만 담습니다.
- 기능과 그 기능의 테스트는 가능하면 같은 커밋에 포함합니다.
- 커밋 수를 늘리기 위해 하나의 일관된 변경을 불필요하게 나누지 않습니다.
- `update`, `fix stuff`, `WIP`처럼 변경 의도를 알 수 없는 메시지는 사용하지 않습니다.
- 설명이 필요하면 본문에 무엇을 했는지보다 왜 필요한지와 주요 선택을 적습니다.
- 관련 issue는 `Refs #12`로 연결하고, 완료되는 issue는 pull request에 `Closes #12`로 연결합니다.
- 공개된 `main`의 커밋 기록은 rebase하거나 force push하지 않습니다.

권장 scope는 `parser`, `analyzer`, `runner`, `cli`, `api`, `web`, `codex`, `release`, `docs`입니다.

```text
feat(parser): resolve nested router prefixes
fix(cli): reject nonexistent repository paths
test(analyzer): cover inherited security dependencies
docs(contributing): define development workflow
ci(actions): update Python test matrix
```

type의 의미는 다음과 같습니다.

- `feat`: 사용자나 호출자가 사용할 수 있는 기능
- `fix`: 잘못된 동작이나 회귀 수정
- `test`: 제품 동작 변경 없이 테스트 추가 또는 정리
- `refactor`: 외부 동작을 유지하는 구조 개선
- `docs`: 문서만 변경
- `chore`: 일반 유지보수
- `ci`: 자동화 workflow 변경
- `build`: 패키징 또는 build 체계 변경

## 개발 환경

아래 명령은 복제한 저장소 루트에서 개발용 가상 환경을 활성화한 상태로 실행합니다.

1. [README의 개발 환경 안내](README.md#개발-환경)에 따라 Python 3.12 가상 환경을 만들고
   활성화합니다.
2. `python -m pip install -e '.[dev]'`로 Python 개발 의존성을 설치합니다.
3. `npm --prefix frontend ci`를 실행해 저장소에 기록된 버전의 frontend 의존성을 설치합니다.
4. 변경 전후에 아래 검증을 실행합니다.

```bash
python -m pytest
ruff check .
ruff format --check .
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
```

문서를 변경했다면 frontend 의존성을 설치한 뒤 저장소 루트에서 다음 검사를 실행합니다.

```bash
node --test scripts/check_docs.test.mjs
node scripts/check_docs.mjs
git ls-files -z '*.md' | xargs -0 frontend/node_modules/.bin/prettier --check
```

검사기는 문서 예제를 실행하지 않고 번역 쌍, 로컬 링크, 명령어의 일치 여부를 검증합니다.
포맷 명령은 Git이 추적하는 Markdown을 검사하므로 새 안내 문서는 최종 확인 전에 staging에 포함합니다.
[포함된 예제](guides/EXAMPLES.md)는 결정론적인 로컬 CLI 시연을 제공합니다.

위에서 frontend를 빌드한 뒤, 같은 가상 환경을 활성화한 상태로 저장소 루트에서 독립 실행 파일을
확인합니다.

```bash
python -m pip install -e '.[build]'
python -m PyInstaller --clean --noconfirm authzest.spec
python scripts/smoke_release.py --binary dist/authzest
```

Windows에서는 `--binary dist/authzest.exe`를 사용합니다. 이 제한된 smoke 검사는 Codex나 스캔 대상 코드를
실행하지 않고 소스 전용 fixture, 리포트 일치, CLI 종료와 이동 복사본을 확인합니다. 일반 사용자 기기의
설치·업그레이드 지원까지 입증하지는 않습니다. 선택 사항인 `doctor`를 명시적으로 실행하면 설치된 Codex CLI의
`codex --version`과 `codex login status`를 호출할 수 있으며 AI 스캔을 시작하지는 않습니다.
로그인 성공이 AI 스캔을 활성화하거나 소스 공유를 승인하지 않습니다. 별도의
[소유 fixture Codex 명령](guides/CODEX_FIXTURE.md)은 opt-in·버전 고정 방식이며 한 소유 fixture의 실제 확인은 성공했지만
일반 저장소 AI는 구현되지 않았습니다.
[CLI 진단 안내](README.md#cli-진단)를 참고하세요.

## 변경 원칙

- `analyzer`, `parser`, `codex`, `runner` 경계를 유지합니다.
- core가 CLI, FastAPI transport, React UI에 의존하지 않게 합니다.
- CLI MVP를 우선하며, 로컬 UI는 core 개발보다 먼저 범위를 확장하지 않고 유지 관리합니다.
- AI 판단 전에 재현 가능하고 결정론적인 분석 결과를 먼저 만듭니다.
- 선택적 AI 설명이나 실제 요청을 보내는 test runner를 추가하기 전에 소스 사실을 수집하고 report,
  인증, 인가의 의미를 정의합니다. `Depends`나 `Security` 선언만으로 접근이 보호된다고 판단하지
  않으며, 근거가 부족하면 `unknown`을 유지합니다.
- 보안 finding에는 source 위치, 근거, 신뢰도와 재현 가능한 최소 테스트를 포함합니다.
- 실제 Codex 연동은 `CodexAdapter` protocol 구현체로 추가하고 core에 SDK나 프로세스 세부사항을
  노출하지 않습니다.
- AI가 결과를 개선한다는 주장은 입증된 장점이 아니라 평가할 가설로 다룹니다.
  [모델 및 평가 전략](development/MODEL_STRATEGY.md)을 따르고 provider·모델 선택은 core 바깥에서 처리합니다.
- 외부 프로세스 실행과 네트워크 요청은 기본적으로 비활성화하며 사용자가 명시적으로 허용해야
  합니다.

## 문서와 번역

프로젝트에서 직접 작성하는 모든 Markdown 문서는 영어 원본과 한국어 번역을 제공합니다. 루트의
프로젝트 `README.md`에는 일본어와 러시아어 번역도 제공합니다. 문서 목차를 포함한 나머지 문서는
영어와 한국어만 필수입니다.

- 관례적인 영어 루트 문서는 유지하고 상세 안내는 `docs/guides/`, `docs/reference/`,
  `docs/development/`, `docs/releases/`에 주제별로 모읍니다.
- 번역은 `docs/i18n/<language>/` 안에서 같은 주제 폴더를 사용하며 파일명 언어 접미사는 붙이지 않습니다.
  예를 들어 `docs/development/BRANCH_RULES.md`의 번역은 `docs/i18n/ko/development/BRANCH_RULES.md`입니다.
- `docs/README.md`의 번역은 프로젝트 README 번역과 충돌하지 않도록 `docs/i18n/ko/INDEX.md`로
  만듭니다. 직접 작성하는 `.github/pull_request_template.md`는
  `docs/i18n/ko/PULL_REQUEST_TEMPLATE.md`와 짝을 이룹니다. GitHub는 계속 영어 템플릿을 기본으로
  불러옵니다.
- 원본과 번역에 서로 연결되는 언어 링크를 넣고, 새 안내 문서를 영어와 한국어 문서 목차에 등록합니다.
- 같은 pull request에서 원본과 모든 번역을 함께 갱신합니다. 지원 동작, 한계, 명령어, 링크와
  체크리스트 상태를 일치시키고 코드 식별자와 명령어 문법은 바꾸지 않습니다.
- 프로젝트 README에는 개요와 시작 방법을 담습니다. 자세한 안내는 `docs/`에 작성하고
  [문서 목차](INDEX.md)에서 연결합니다.
- 릴리스의 실제 발행과 공개 파일 검증 후, 후속 문서 PR에서 README들과 영·한 안내의 발행 상태,
  다운로드 링크, 완료된 체크리스트와 검증 한계를 맞춥니다. 이 변경은 `Unreleased`에 기록하고
  배포한 태그나 산출물은 다시 쓰지 않습니다.

이 정책은 기여용 템플릿을 포함해 저장소를 위해 직접 작성하는 Markdown에 적용합니다. 생성 결과물과
외부 의존성 문서는 프로젝트 안내 문서로 번역하거나 커밋하지 않습니다.

## 완료 조건

Pull request를 병합하려면 다음 조건을 만족해야 합니다.

- 연결된 issue의 완료 조건을 충족했습니다.
- 이슈·PR의 라벨·담당자·마일스톤 또는 기록된 공통 작업 예외를 지정하고 실제 값을 확인했습니다.
- 새 동작 또는 수정된 동작을 검증하는 테스트가 있습니다.
- Python과 frontend의 관련 로컬 검사가 통과했습니다.
- 문서를 변경했다면 문서 검사기 테스트, 번역·링크 검사, Markdown 포맷 검사가 통과했습니다.
- 사용자에게 보이는 동작이 바뀌었다면 관련 문서를 함께 수정했습니다.
- 문서를 수정했다면 해당 번역과 정상 동작하는 언어 링크를 함께 반영했습니다.
- 보안 영향과 하위 호환성 영향을 pull request에 기록했습니다.
- 비밀키, 개인정보, 생성 파일을 커밋하지 않았습니다.
- GitHub Actions의 필수 검사가 통과했습니다.

버그와 기능 제안은 재현 절차, 기대 결과, 실제 결과, 실행 환경을 포함해 issue로 남겨 주세요.
보안 취약점은 공개 issue 대신 [한국어 보안 정책](SECURITY.md)의 절차를 따라 주세요.
