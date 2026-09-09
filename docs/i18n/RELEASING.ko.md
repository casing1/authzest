# AuthZest 릴리스 관리

[문서](INDEX.ko.md) · [English](../RELEASING.md) · 한국어

AuthZest는 GitHub Releases를 통해 독립 실행 파일을 배포합니다. 현재 릴리스 절차에는 PyPI나 npm 패키지
배포가 포함되지 않습니다. 바이너리에는 서명이나 notarization이 적용되어 있지 않습니다.

## 배포된 preview와 현재 소스

현재 배포된 preview는 [v0.1.0-alpha.1](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1)입니다.
[파서 지원 범위](PARSER_SCOPE.ko.md)에 설명된 FastAPI 객체 식별, 라우터 prefix 합성, 다른 파일의 import 해석은
그 이후 추가되었으며 아직 [`Unreleased`](CHANGELOG.ko.md#unreleased)에 있습니다. 이 기능들은 현재 소스에서
사용할 수 있으며, 해당 preview 바이너리에 포함되어 있지 않습니다.

현재 소스의 `pyproject.toml` 버전도 여전히 `0.1.0a1`입니다. 다음 릴리스를 준비하면서 버전을 올리기 전에는
`authzest --version`만으로 preview와 소스 설치본을 구분할 수 없습니다. 소스 빌드의 동작을 보고할 때는
`git rev-parse HEAD`로 소스 커밋도 기록하세요.

## 버전 정책

Semantic Versioning을 사용합니다. 초기 개발 단계인 `1.0.0` 미만에서는 호환성이 깨지는 변경이 생길 수
있습니다.

Python 패키지 메타데이터에는 PEP 440 표기를, Git 태그에는 SemVer 표기를 사용합니다. 아래는 표기 대응
예시이며 다음 릴리스 버전을 미리 정한 것이 아닙니다.

| 릴리스 단계 | `pyproject.toml` | Git 태그         |
| ----------- | ---------------- | ---------------- |
| Alpha       | `0.1.0a1`        | `v0.1.0-alpha.1` |
| Beta        | `0.1.0b1`        | `v0.1.0-beta.1`  |
| Candidate   | `0.1.0rc1`       | `v0.1.0-rc.1`    |
| Final       | `0.1.0`          | `v0.1.0`         |

Python 런타임과 API 버전의 기준은 [`pyproject.toml`](../../pyproject.toml)입니다. `private: true`로 설정된
frontend 패키지는 별도로 버전을 관리하지 않습니다. 새 릴리스마다 사용하지 않은 새 버전을
선택하세요. 이미 배포한 `v0.1.0-alpha.1` 태그를 다시 발행하면 안 됩니다.

## 릴리스 준비

프로젝트 개발 환경을 활성화한 뒤 저장소 루트에서 아래 명령을 실행합니다. 명령 예시는 Bash 기준입니다.
Windows에서는 Git Bash로 실행하고, 로컬 빌드를 확인할 때 `.exe` 실행 파일을 사용하세요.

1. 예정 버전, 범위, 완료 조건을 담은 릴리스 이슈를 만듭니다. 버전을 정하기 전에 기존
   [릴리스](https://github.com/casing1/authzest/releases)와 태그를 확인합니다.
2. 최신 `main`에서 짧게 유지할 작업 브랜치를 만듭니다.
3. `pyproject.toml`의 `project.version`을 수정합니다.
4. [`CHANGELOG.md`](../../CHANGELOG.md)의 `Unreleased`에서 완료된 변경을
   `## [X.Y.Z-alpha.N] - YYYY-MM-DD`와 같은 날짜가 있는 제목 아래로 옮깁니다.
   [한국어 변경 이력](CHANGELOG.ko.md)의 버전, 날짜, 링크도 함께 맞춥니다.
5. 아래 자리표시자를 이슈에서 정한 미사용 태그로 바꿉니다. 새 패키지 버전과 정확히 대응해야 합니다.
   자리표시자를 그대로 두면 검증이 실패하도록 되어 있습니다.

   ```bash
   AUTHZEST_NEXT_TAG='vX.Y.Z-alpha.N'
   ```

6. 릴리스 검사를 실행합니다.

   `doctor`는 설치된 Codex CLI의 진단 명령인 `codex --version`과 `codex login status`를 실행할 수 있습니다.
   AI 분석을 시작하지 않으며, Codex가 없거나 로그인하지 않았다면 경고가 나옵니다.

   ```bash
   python -m pip install -e '.[dev,build]'
   ruff check .
   ruff format --check .
   pytest

   cd frontend
   npm ci
   npm run lint
   npm run format:check
   npm run build
   cd ..

   python scripts/verify_release.py "${AUTHZEST_NEXT_TAG:?Set the unused release tag first}"
   git grep -F "## [${AUTHZEST_NEXT_TAG#v}] - " -- CHANGELOG.md
   python -m PyInstaller --clean --noconfirm authzest.spec
   ./dist/authzest --version
   ./dist/authzest doctor
   ```

   [`verify_release.py`](../../scripts/verify_release.py)는 태그와 패키지 버전이 정확히 대응하는지만 검사합니다.
   변경 이력은 검사하지 않습니다. 별도 제목 확인과 영어·한국어 변경 이력의 검토는 관리자가 수행해야 합니다.
   날짜와 해당 버전에 포함된 변경도 확인하세요.

7. PR을 만들고 필수 CI와 CodeQL 검사가 통과한 뒤 병합합니다.
8. 배포 전에 `main`에서 릴리스 워크플로를 실행하여 세 플랫폼의 빌드를 검증합니다.

   ```bash
   gh workflow run release.yml --ref main
   ```

   [GitHub Actions](https://github.com/casing1/authzest/actions/workflows/release.yml)에서 해당 실행을 확인하고
   아티팩트를 내려받아 기본 동작을 점검합니다. `main`에서 수동 실행하면 릴리스를 만들지 않고 아티팩트만
   빌드합니다. 태그를 지정한 수동 실행은 dry run이 아닙니다. 배포 조건은 실행 대상 ref가 태그인지에 따라
   결정됩니다.

9. 수동 `main` 실행이 성공하고 아티팩트의 기본 동작을 확인한 뒤, 해당 실행의 전체 `headSha`를 확인합니다.
   아래 `RUN_ID`를 해당 실행 ID로 바꾸고 `status`가 `completed`, `conclusion`이 `success`인지 확인한 다음,
   반환된 전체 SHA를 `AUTHZEST_VERIFIED_COMMIT`에 복사합니다.

   ```bash
   gh run view RUN_ID --json headSha,status,conclusion
   AUTHZEST_VERIFIED_COMMIT='COPY_THE_SUCCESSFUL_MAIN_RUN_HEAD_SHA_HERE'
   ```

   성공한 실행의 커밋을 사용해야 하며, 최신 로컬 SHA로 대신하면 안 됩니다. 이후 `main`이 바뀌면 새로운
   커밋에서 워크플로와 아티팩트 검증을 다시 수행한 뒤 이 값을 갱신합니다.

## 배포

검증한 `main` 커밋에 정확히 태그를 붙입니다. 준비 단계에서 정한 `AUTHZEST_NEXT_TAG`와
`AUTHZEST_VERIFIED_COMMIT` 값을 모두 유지하세요. 아래 예시는 작업 트리가 깨끗하지 않거나, 검증한 실행에서
빌드한 커밋이 아니거나, 버전·변경 이력이 맞지 않거나, 태그가 이미 존재하면 중단합니다.

```bash
(
  set -e
  : "${AUTHZEST_NEXT_TAG:?Set the unused release tag first}"
  : "${AUTHZEST_VERIFIED_COMMIT:?Copy the successful main workflow headSha first}"
  test -z "$(git status --porcelain)"
  git switch main
  git pull --ff-only origin main
  git fetch --tags origin
  test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
  test "$(git rev-parse HEAD)" = "$AUTHZEST_VERIFIED_COMMIT"
  python scripts/verify_release.py "$AUTHZEST_NEXT_TAG"
  git grep -F "## [${AUTHZEST_NEXT_TAG#v}] - " -- CHANGELOG.md
  if git show-ref --verify --quiet "refs/tags/$AUTHZEST_NEXT_TAG"; then
    printf 'Refusing to reuse existing tag: %s\n' "$AUTHZEST_NEXT_TAG"
    exit 1
  fi
  git tag -a "$AUTHZEST_NEXT_TAG" "$AUTHZEST_VERIFIED_COMMIT" -m "AuthZest $AUTHZEST_NEXT_TAG"
  git push origin "refs/tags/$AUTHZEST_NEXT_TAG"
)
```

[릴리스 워크플로](../../.github/workflows/release.yml)는 검증 단계가 실행되는 시점에 태그가 원격 `main`의
최신 커밋을 가리키는지 확인합니다. 로컬 확인 이후에도 `main`이 바뀔 수 있으므로 검증이 끝날 때까지 다른
병합 일정을 조율하세요. 검증 전에 `main`이 바뀌어 실패했다면 태그를 이동하거나 덮어쓰지 말고, 실패한
시도를 기록한 뒤 검증된 최신 `main`에서 새 버전을 준비합니다.

워크플로는 검증 과정에서 Python과 frontend 품질 검사를 다시 실행하고, 대시보드 자산을 포함한 Linux,
macOS, Windows 실행 파일과 각 바이너리의 `.sha256` 파일을 만듭니다. 자산 이름에는 릴리스 버전, 운영체제,
빌드 시 확인한 아키텍처가 들어갑니다. prerelease 접미사가 있는 태그는 GitHub prerelease를 만들고,
최종 버전 태그는 일반 릴리스를 만듭니다. Python·npm 패키지 배포와 바이너리 서명은 수행하지 않습니다.

## 검증과 복구

- 모든 릴리스 자산과 그에 대응하는 `.sha256` 파일을 내려받습니다.
- macOS나 Linux에서는 두 파일이 있는 디렉터리에서 `shasum -a 256 -c <asset>.sha256`을 실행합니다.
  `<asset>`은 실제 파일 이름으로 바꿉니다. Windows에서는 `Get-FileHash -Algorithm SHA256` 결과와 해당
  manifest를 비교합니다. checksum은 파일 무결성을 확인하며 게시자의 신원을 증명하지는 않습니다.
- 최소 한 곳의 깨끗한 환경에서 내려받은 실행 파일의 `--version`과 `doctor`를 실행합니다. checksum을 확인한
  뒤 macOS/Linux에서 사용할 정확한 다운로드 파일에 실행 권한을 추가합니다. 다운로드 디렉터리에서 파일 이름
  자리표시자를 바꾸고 실행하세요.

  ```bash
  AUTHZEST_DOWNLOADED_BINARY='REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME'
  chmod u+x "./$AUTHZEST_DOWNLOADED_BINARY"
  "./$AUTHZEST_DOWNLOADED_BINARY" --version
  "./$AUTHZEST_DOWNLOADED_BINARY" doctor
  ```

  Windows `.exe` 파일에는 `chmod`가 필요하지 않습니다. 다운로드 디렉터리의 PowerShell에서 정확히 내려받은
  파일을 선택해 실행하세요.

  ```powershell
  $AuthZestDownloadedBinary = '.\REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME.exe'
  & $AuthZestDownloadedBinary --version
  & $AuthZestDownloadedBinary doctor
  ```

  특정 플랫폼의 설치를 검증했다고 설명하려면 그 플랫폼에서도 확인해야 합니다. 로컬 검사와 마찬가지로
  `doctor`는 설치된 Codex 진단 명령을 실행할 수 있으며, Codex가 없거나 로그인하지 않았다면 경고가 나올 수
  있습니다.

- 자동 생성된 GitHub 릴리스 노트와 두 언어의 변경 이력이 올바른 버전과 기능을 설명하는지 확인합니다.
  `main`의 빌드 아티팩트는 자동으로 공개 릴리스가 되는 것이 아닙니다.
- 빌드나 배포가 실패하면 재시도 전에 실패한 작업을 확인합니다. 일시적인 실패라면 같은 태그와 커밋을
  유지하면서, 해당 커밋이 여전히 검증 조건을 만족할 때 재시도할 수 있습니다. 사용자가 이미 내려받았을 수
  있는 릴리스를 자산 덮어쓰기 옵션으로 조용히 교체하지 마세요.
- 기존 릴리스 태그를 이동하거나 덮어쓰지 않습니다. 배포된 릴리스에 문제가 있다면 이슈와 변경 이력에
  기록하고 새 patch 또는 prerelease 버전을 배포합니다.

워크플로는 모든 빌드 실행 파일에 대해 버전 명령을 실행합니다. 깨끗한 환경에서의 설치, 다운로드 후
checksum 확인, 변경 이력 검토, 릴리스 노트의 정확성은 관리자가 확인해야 하며 모두 자동으로 보장되는 것은
아닙니다.
