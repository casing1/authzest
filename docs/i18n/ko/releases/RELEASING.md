# AuthZest 릴리스 관리

[문서](../INDEX.md) · [English](../../../releases/RELEASING.md) · 한국어

AuthZest는 GitHub Releases를 통해 독립 실행 파일을 배포합니다. 현재 릴리스 절차에는 PyPI나 npm 패키지
배포가 포함되지 않습니다. 바이너리에는 서명이나 notarization이 적용되어 있지 않습니다.

## 배포된 preview와 현재 소스

### Alpha.3 준비 (아직 미발행)

[#56](https://github.com/casing1/authzest/issues/56)은 [PR #55](https://github.com/casing1/authzest/pull/55)
이후 패키지 `0.1.0a3` / 태그 `v0.1.0-alpha.3`를 준비합니다. 오프라인 근거/제안 계약, opt-in
버전 고정 Codex fixture 초안, 승인형 복사본 변경, 소스 설정 검사와 별도 승인한 고정 런타임 검사를
묶은 중간 배포이며 scan report schema는 `1.2`입니다. [제한적 완료 검사](../guides/RUNTIME_VERIFICATION.md)는
로컬에서 통과했지만 정확한 main의 세 플랫폼 빌드·새 다운로드 artifact·공개 산출물 검증은
게시 전에 통과해야 합니다. Windows 런타임은 미지원이고 기존 Windows scan 지원은 유지하며
릴리스 준비가 새 실제 Codex 호출을 승인하지 않습니다. 별도 발행 후 문서 PR로 새 배포를 확인할
때까지 아래 alpha.2 다운로드 기록을 유지하며 기존 태그/산출물을 이동하거나 교체하지 않습니다.

### 발행된 alpha.2

[v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2)는 2026-09-10에 Python
패키지 `0.1.0a2`, 리포트 스키마 `1.2`로 발행됐습니다. 커밋은 `7cc359acbb864ef6d31e3b536787857da4f7e09c`이며
[준비 PR #40](https://github.com/casing1/authzest/pull/40), [완료된 릴리스 이슈 #39](https://github.com/casing1/authzest/issues/39)에
연결됩니다. 안정화된 보안 제품이 아닌 알파 프리릴리스입니다. 이후 `main`의 소스/문서 변경은 해당 태그나 산출물을 바꾸지 않습니다.
첫 [v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1)에는
[파서 범위](../reference/PARSER_SCOPE.md)와 [alpha.2 변경 이력](../CHANGELOG.md#010-alpha2---2026-09-10)의
파서·리포트·의존성 개선이 없습니다. 소스 빌드의 동작을 보고할 때는 `git rev-parse HEAD`로 커밋도 기록하세요.

### Alpha.2 검증 기록

[main 사전 실행 34442310332](https://github.com/casing1/authzest/actions/runs/34442310332)과
[태그 발행 실행 34442837616](https://github.com/casing1/authzest/actions/runs/34442837616)은 위의 정확한 커밋에서
통과했습니다. Python 테스트 451개, 문서 검사기 테스트 14개, frontend lint/format·빌드,
소스 전용 fixture 4종, 리포트 일치, strict/잘못된 입력 종료와 이동한 바이너리를 검사했습니다.
별도 새 job에서 AuthZest의 Python 의존성을 설치하지 않고 각 산출물을 내려받아 확인했습니다.

| 플랫폼      | 공개 실행 파일                           |
| ----------- | ---------------------------------------- |
| Linux x64   | `authzest-0.1.0-alpha.2-linux-x64`       |
| macOS arm64 | `authzest-0.1.0-alpha.2-macos-arm64`     |
| Windows x64 | `authzest-0.1.0-alpha.2-windows-x64.exe` |

각 실행 파일에는 대응하는 `.sha256` manifest가 있으며 총 실행 파일 3개와 manifest 3개입니다.
공개 파일을 모두 다시 내려받아 체크섬을 확인했습니다. 공개된 macOS 파일은 프로젝트 의존성이 설치되지 않은
Python 환경에서 로컬 격리 복사본 fixture 검사도 통과했습니다. 이 기록은 일반 사용자 기기의 깨끗한 설치·업그레이드,
모든 OS/Python/FastAPI 버전 호환성, 서명·공증이나 인가 정확성을 입증하지 않습니다. smoke 검사에 Codex 호출,
스캔 대상 앱 실행이나 사용자 소스 수정은 포함하지 않았습니다.

## 버전 정책

릴리스 시점은 관리자 재량의 기능 단계 기준이며 이슈마다 태그를 만들거나 고정 달력 주기로 내지 않습니다.
관리자는 2026-09-11에 시점 판단을 위임했지만 아래 릴리스 검사를 생략한다는 뜻은 아닙니다.
#33/#46 같은 내부 계약은 사용자에게 의미 있는 기능 단위와 산출물/호환성 검증이 준비될 때까지
`Unreleased`에 둡니다. 제한된 #35 흐름을 시연할 수 있는 시점이 다음 후보이며 날짜나 버전을 미리
약속하지 않습니다. 개발 7주와 별도 시험/제출 여유를 지키며 활동량을 늘리기 위한 배포는 하지 않습니다.

Semantic Versioning을 사용합니다. 초기 개발 단계인 `1.0.0` 미만에서는 호환성이 깨지는 변경이 생길 수
있습니다.

Python 패키지 메타데이터에는 PEP 440 표기를, Git 태그에는 SemVer 표기를 사용합니다. 아래는 표기 대응
예시이며 다음 릴리스 버전을 미리 정한 것이 아닙니다.

| 릴리스 단계 | `pyproject.toml` | Git 태그         |
| ----------- | ---------------- | ---------------- |
| Alpha       | `0.1.0a2`        | `v0.1.0-alpha.2` |
| Beta        | `0.1.0b1`        | `v0.1.0-beta.1`  |
| Candidate   | `0.1.0rc1`       | `v0.1.0-rc.1`    |
| Final       | `0.1.0`          | `v0.1.0`         |

Python 런타임과 API 버전의 기준은 [`pyproject.toml`](../../../../pyproject.toml)입니다. `private: true`로 설정된
frontend 패키지는 별도로 버전을 관리하지 않습니다. 새 릴리스마다 사용하지 않은 새 버전을
선택하세요. 이미 배포한 `v0.1.0-alpha.1`과 `v0.1.0-alpha.2`는 모두 다시 발행하면 안 됩니다.

## 릴리스 준비

프로젝트 개발 환경을 활성화한 뒤 저장소 루트에서 아래 명령을 실행합니다. 명령 예시는 Bash 기준입니다.
Windows에서는 Git Bash로 실행하고, 로컬 빌드를 확인할 때 `.exe` 실행 파일을 사용하세요.

1. 예정 버전, 범위, 완료 조건을 담은 릴리스 이슈를 만듭니다. 버전을 정하기 전에 기존
   [릴리스](https://github.com/casing1/authzest/releases)와 태그를 확인합니다.
2. 최신 `main`에서 짧게 유지할 작업 브랜치를 만듭니다.
3. `pyproject.toml`의 `project.version`을 수정합니다.
4. [`CHANGELOG.md`](../../../../CHANGELOG.md)의 `Unreleased`에서 완료된 변경을
   `## [X.Y.Z-alpha.N] - YYYY-MM-DD`와 같은 날짜가 있는 제목 아래로 옮깁니다.
   [한국어 변경 이력](../CHANGELOG.md)의 버전, 날짜, 링크도 함께 맞춥니다.
5. 아래 자리표시자를 이슈에서 정한 미사용 태그로 바꿉니다. 새 패키지 버전과 정확히 대응해야 합니다.
   자리표시자를 그대로 두면 검증이 실패하도록 되어 있습니다.

   ```bash
   AUTHZEST_NEXT_TAG='vX.Y.Z-alpha.N'
   ```

6. 릴리스 검사를 실행합니다.

   스캔 smoke 검사는 `doctor`, Codex나 대상 애플리케이션 코드를 실행하지 않습니다.
   의존성 설치와 산출물 다운로드는 네트워크에 접근할 수 있습니다.

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
   python scripts/smoke_release.py --binary dist/authzest
   python scripts/smoke_fixture_runtime.py --binary dist/authzest
   ```

   [`verify_release.py`](../../../../scripts/verify_release.py)는 정확한 태그/패키지 버전 대응, 영한 변경 이력마다
   하나의 대응 날짜 제목, 유효하고 같은 날짜와 비어 있지 않은 내용을 확인합니다. 배포 여부나 번역/기능
   내용의 정확성까지 입증하지 않으므로 항목도 검토하세요. 기본 한국어 경로는 `docs/i18n/ko/CHANGELOG.md`입니다.

   [`smoke_release.py`](../../../../scripts/smoke_release.py)는 버전/help/텍스트, checkout core와 스키마 `1.2`
   JSON 동등성, 유지하는 소스 전용 fixture 4개, bounded strict 종료 0, partial 기본/strict 종료 0/1과
   잘못된 루트 종료 2를 확인합니다. binary 모드는 선택한 실행 파일과 별도 작업 디렉터리·정리한 Python
   환경에서 이동한 임시 복사본을 검사합니다. Windows에서는 `--binary dist/authzest.exe`를 사용합니다.
   명령별 timeout 기본값은 45초이며 `--expected-version`으로 `pyproject.toml` 대신 예상 PEP 440 버전을
   지정할 수 있습니다.

   별도 [런타임 smoke](../guides/RUNTIME_VERIFICATION.md)는 실제 native 부모·worker와 이동한
   복사본에서 고정 내장 AFTER fixture를 검사합니다. POSIX는 정확한 debug/ASGI health 관찰에
   성공해야 하며 Windows는 worker 없이 지원 불가를 반환해야 합니다. Codex를 호출하거나
   사용자 소스를 받지 않습니다. 외부 제한은 45초이고 worker 시작·I/O는 5초와 별도 정리 1초
   제한을 유지합니다. 이는 OS sandbox가 아닙니다.

7. PR을 만들고 필수 CI와 CodeQL 검사가 통과한 뒤 병합합니다.
8. 배포 전에 `main`에서 릴리스 워크플로를 실행하여 세 플랫폼의 빌드를 검증합니다.

   ```bash
   gh workflow run release.yml --ref main
   ```

   [GitHub Actions](https://github.com/casing1/authzest/actions/workflows/release.yml)에서 해당 실행을 확인하고
   아티팩트를 내려받아 기본 동작을 점검합니다. `main`에서 수동 실행하면 릴리스를 만들지 않고 아티팩트만
   빌드합니다. 태그를 지정한 수동 실행은 dry run이 아닙니다. 배포 조건은 실행 대상 ref가 태그인지에 따라
   결정됩니다.

   이 checkout에서 다운로드한 플랫폼별 산출물 디렉터리를 대응 OS에서 각각 확인합니다.

   ```bash
   python scripts/smoke_release.py --artifact-dir /path/to/ONE_PLATFORM_ARTIFACT_DIRECTORY
   python scripts/smoke_fixture_runtime.py --artifact-dir /path/to/ONE_PLATFORM_ARTIFACT_DIRECTORY
   ```

   artifact 모드는 실행 파일 하나와 대응 `.sha256` manifest를 요구하고 checksum 확인 뒤 이동한 임시
   복사본만 실행합니다. 다운로드 원본은 수정하거나 실행하지 않습니다. 리포트 비교에 checkout의 core와
   fixture를 쓰므로 checkout을 해당 빌드의 커밋에 맞추세요.

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

[릴리스 워크플로](../../../../.github/workflows/release.yml)는 검증 단계가 실행되는 시점에 태그가 원격 `main`의
최신 커밋을 가리키는지 확인합니다. 로컬 확인 이후에도 `main`이 바뀔 수 있으므로 검증이 끝날 때까지 다른
병합 일정을 조율하세요. 검증 전에 `main`이 바뀌어 실패했다면 태그를 이동하거나 덮어쓰지 말고, 실패한
시도를 기록한 뒤 검증된 최신 `main`에서 새 버전을 준비합니다.

워크플로는 검증 과정에서 Python과 frontend 품질 검사를 다시 실행하고, 대시보드 자산을 포함한 Linux,
macOS, Windows 실행 파일을 빌드하고 바이너리/이동 복사본의 fixture smoke 검사를 수행하며 각 바이너리의
`.sha256` 파일을 만듭니다. 버전이 있는 산출물도 checksum을 확인하는 smoke 검사를 거칩니다.
별도의 새 job은 플랫폼별 산출물을 다운로드하고 Python 환경에 AuthZest가 설치되지 않았는지 확인한 뒤,
프로젝트 패키지 설치 없이 Python 격리 모드(`-I`)로 artifact smoke를 실행합니다. 배포에는 검증·빌드·모든
새 artifact 검증 job의 통과가 필요합니다. 이 검사도 사용자 기기의 깨끗한 설치나 업그레이드를 입증하지 않습니다.
자산 이름에는 릴리스 버전, 운영체제,
빌드 시 확인한 아키텍처가 들어갑니다. prerelease 접미사가 있는 태그는 GitHub prerelease를 만들고,
최종 버전 태그는 일반 릴리스를 만듭니다. Python·npm 패키지 배포와 바이너리 서명은 수행하지 않습니다.

## 검증과 복구

- 모든 릴리스 자산과 그에 대응하는 `.sha256` 파일을 내려받습니다.
- macOS나 Linux에서는 두 파일이 있는 디렉터리에서 `shasum -a 256 -c <asset>.sha256`을 실행합니다.
  `<asset>`은 실제 파일 이름으로 바꿉니다. Windows에서는 `Get-FileHash -Algorithm SHA256` 결과와 해당
  manifest를 비교합니다. checksum은 파일 무결성을 확인하며 게시자의 신원을 증명하지는 않습니다.
- 깨끗한 환경에서 내려받은 실행 파일의 `--version`, `--help`와 유지하는 fixture 스캔을 실행합니다. checksum을 확인한
  뒤 macOS/Linux에서 사용할 정확한 다운로드 파일에 실행 권한을 추가합니다. 다운로드 디렉터리에서 파일 이름
  자리표시자를 바꾸고 실행하세요.

  ```bash
  AUTHZEST_DOWNLOADED_BINARY='REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME'
  chmod u+x "./$AUTHZEST_DOWNLOADED_BINARY"
  "./$AUTHZEST_DOWNLOADED_BINARY" --version
  "./$AUTHZEST_DOWNLOADED_BINARY" --help
  ```

  Windows `.exe` 파일에는 `chmod`가 필요하지 않습니다. 다운로드 디렉터리의 PowerShell에서 정확히 내려받은
  파일을 선택해 실행하세요.

  ```powershell
  $AuthZestDownloadedBinary = '.\REPLACE_WITH_THE_EXACT_DOWNLOADED_FILENAME.exe'
  & $AuthZestDownloadedBinary --version
  & $AuthZestDownloadedBinary --help
  ```

  특정 플랫폼의 깨끗한 설치나 업그레이드를 검증했다고 설명하려면 그 플랫폼에서 확인해야 합니다.
  검토한 fixture를 그 환경에 복사하고 [소스 전용 예제](../guides/EXAMPLES.md)의 명령을 사용하세요.
  `doctor`는 선택 사항이며 설치된 Codex 진단 명령을 실행할 수 있습니다. 릴리스 smoke의 필수 조건은 아닙니다.

- 자동 생성된 GitHub 릴리스 노트와 두 언어의 변경 이력이 올바른 버전과 기능을 설명하는지 확인합니다.
  `main`의 빌드 아티팩트는 자동으로 공개 릴리스가 되는 것이 아닙니다.
- 발행과 공개 파일 검증 후 최신 `main`에서 문서 후속 이슈/PR을 만듭니다. README 네 언어와 영·한 안내의
  준비 단계 표현 및 이전 다운로드 링크를 바꿉니다. 릴리스 URL·날짜·정확한 커밋·실제 검사와 남은 한계를 기록하고
  개발 계획/로드맵은 충족한 조건만 완료로 바꿉니다. 발행 이후 문서 변경은 `Unreleased`에 남기고 문서 검사와
  필수 CI를 통과해 병합합니다. 이 후속 작업만으로 태그를 이동하거나 산출물을 교체하거나 새 버전을 발행하지 않습니다.
  발행 전에는 조건부 표현을 유지하세요. 예정된 버전이나 dry run 성공만으로 공개 릴리스가 되는 것은 아닙니다.
- 빌드나 배포가 실패하면 재시도 전에 실패한 작업을 확인합니다. 일시적인 실패라면 같은 태그와 커밋을
  유지하면서, 해당 커밋이 여전히 검증 조건을 만족할 때 재시도할 수 있습니다. 사용자가 이미 내려받았을 수
  있는 릴리스를 자산 덮어쓰기 옵션으로 조용히 교체하지 마세요.
- 기존 릴리스 태그를 이동하거나 덮어쓰지 않습니다. 배포된 릴리스에 문제가 있다면 이슈와 변경 이력에
  기록하고 새 patch 또는 prerelease 버전을 배포합니다.

워크플로의 격리된 이동 복사본 검사는 깨끗한 컴퓨터의 설치나 업그레이드 테스트가 아닙니다.
지원한다고 안내하는 플랫폼마다 다운로드 산출물을 별도로 확인하고 릴리스 노트/내용의 정확성을 검토하세요.
서명/공증, 일반적인 FastAPI 호환성이나 접근통제 정확성은 이 smoke 검사로 입증되지 않습니다.
정확히 선택한 SHA에서 필수 실행과 산출물 검증을 통과한 뒤에만 배포하세요.
