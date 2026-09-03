<p align="center">
  <a href="../../CONTRIBUTING.md">English</a> ·
  <strong>한국어</strong>
</p>

# AuthZest 기여 안내

AuthZest는 작고 검증 가능한 변경을 꾸준히 병합하는 방식으로 개발합니다. 기능 수보다 변경 이유,
검증 과정, 보안상 판단이 이력에 명확히 남는 것을 우선합니다.

## 작업 흐름

1. 구현 전에 GitHub issue를 만들고 문제, 범위, 완료 조건을 적습니다.
2. 최신 `main`에서 issue 번호가 포함된 짧은 작업 브랜치를 만듭니다.
3. 한 가지 목적에 집중해 구현하고 같은 변경에서 테스트를 추가합니다.
4. 로컬 검증을 통과시킨 뒤 의미 있는 단위로 커밋합니다.
5. issue를 연결한 pull request를 열고 CI 결과를 확인합니다.
6. 대화와 CI가 정리되면 merge commit으로 병합하고 작업 브랜치를 삭제합니다.

`main`에는 직접 push하지 않으며 항상 실행 가능하고 테스트를 통과하는 상태를 유지합니다.

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
`develop` 브랜치는 두지 않습니다. 릴리스는 검증된 `main` 커밋에 `v0.1.0-alpha.1` 같은 태그를
붙여 만듭니다. [릴리스 안내](../RELEASING.md)를 따르며 공개된 태그는 변경하지 않습니다.

## 커밋 규칙

[Conventional Commits](https://www.conventionalcommits.org/)의 간단한 형태를 사용합니다.

```text
<type>(<scope>): <summary>
```

- summary는 명령형 영문으로 작성하고 마침표 없이 72자 이내로 제한합니다.
- 커밋 하나에는 되돌리거나 검토할 수 있는 한 가지 논리적 변경만 담습니다.
- 기능과 그 기능의 테스트는 가능하면 같은 커밋에 포함합니다.
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

1. Python 3.12 가상 환경을 만듭니다.
2. `python -m pip install -e '.[dev]'`로 Python 개발 의존성을 설치합니다.
3. `frontend/`에서 `npm install`을 실행합니다.
4. 변경 전후에 아래 검증을 실행합니다.

```bash
pytest
ruff check .
ruff format --check .
cd frontend && npm run lint && npm run format:check && npm run build
```

독립 실행 파일을 확인하려면 frontend를 빌드한 뒤 아래 명령을 실행합니다.

```bash
python -m pip install -e '.[build]'
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest doctor
```

## 변경 원칙

- `analyzer`, `parser`, `codex`, `runner` 경계를 유지합니다.
- core가 CLI, FastAPI transport, React UI에 의존하지 않게 합니다.
- AI 판단 전에 재현 가능하고 결정론적인 분석 결과를 먼저 만듭니다.
- 보안 finding에는 source 위치, 근거, 신뢰도와 재현 가능한 최소 테스트를 포함합니다.
- 실제 Codex 연동은 `CodexAdapter` protocol 구현체로 추가하고 core에 SDK나 프로세스 세부사항을
  노출하지 않습니다.
- 외부 프로세스 실행과 네트워크 요청은 기본적으로 비활성화하며 사용자가 명시적으로 허용해야
  합니다.

## 완료 조건

Pull request를 병합하려면 다음 조건을 만족해야 합니다.

- 연결된 issue의 완료 조건을 충족했습니다.
- 새 동작 또는 수정된 동작을 검증하는 테스트가 있습니다.
- Python과 frontend의 관련 로컬 검사가 통과했습니다.
- 사용자에게 보이는 동작이 바뀌었다면 관련 문서를 함께 수정했습니다.
- 보안 영향과 하위 호환성 영향을 pull request에 기록했습니다.
- 비밀키, 개인정보, 생성 파일을 커밋하지 않았습니다.
- GitHub Actions의 필수 검사가 통과했습니다.

버그와 기능 제안은 재현 절차, 기대 결과, 실제 결과, 실행 환경을 포함해 issue로 남겨 주세요.
보안 취약점은 공개 issue 대신 [한국어 보안 정책](SECURITY.ko.md)의 절차를 따라 주세요.
