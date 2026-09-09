<p align="center">
  <a href="../BRANCH_RULES.md">English</a> ·
  <strong>한국어</strong>
</p>

# 브랜치 보호

[문서 목차](INDEX.ko.md) · [기여 안내](CONTRIBUTING.ko.md)

활성화된 [Protect main ruleset](https://github.com/casing1/authzest/rules/22200692)은 저장소의 기본
브랜치에 적용됩니다. 규칙은 저장소 설정에서 강제하며, 이 문서는 정책을 설명할 뿐 설정을 직접
적용하지 않습니다.

- 변경은 pull request를 거쳐 merge commit으로 병합해야 합니다.
- pull request는 기준 브랜치의 최신 상태를 반영해야 하며 리뷰 대화를 해결해야 합니다.
- 필수 검사는 `python`, `frontend`, `CodeQL`입니다.
- `CodeQL` 결과는 GitHub Advanced Security에서 제공해야 합니다. integration ID는 `57789`입니다.
- 강제 push와 브랜치 삭제를 차단하며, 우회 권한이 있는 사용자나 앱은 설정하지 않습니다.
- 현재 개인 개발 흐름에서는 필수 승인 리뷰 수를 0명으로 유지합니다.

## 보호된 브랜치에서 작업하기

roadmap 항목과 완료 조건이 명확한 개별 issue에서 시작합니다. 최신 `main`에서 짧은 작업 브랜치를
만들고, 기능과 테스트를 함께 구현한 뒤 의미 있는 단위로 커밋합니다. issue를 연결하고 검증 결과와
관련 문서·번역 변경을 포함한 pull request를 엽니다.

병합 전에 현재 변경의 `python`, `frontend`, `CodeQL` 검사 통과를 확인하고 리뷰 대화를 해결합니다.
필요하면 기준 브랜치의 최신 변경도 반영합니다. merge commit으로 병합한 뒤 작업 브랜치를
삭제합니다. 커밋 수를 늘리기 위해 일관된 변경을 불필요하게 나누지 않습니다. 필수 승인 리뷰 수가
0명이더라도 필수 검사가 면제되지는 않습니다.

## 규칙 유지 관리

CodeQL은 GitHub의 기존 default setup으로 설정돼 있습니다. `.github/workflows/ci.yml`에 선언돼
있지 않아도 pull request의 CodeQL 결과는 필수입니다. 검사가 실패하거나 병합을 차단하는 finding을
보고하면 병합 전에 해결합니다. 관련 없는 변경을 통과시키려고 이 요구사항을 제거하지 않습니다.

검사 이름이나 스캔 설정을 바꿀 때는 새 검사가 pull request에 나타나는지 먼저 확인한 뒤 ruleset을
갱신합니다. 기존 보호 설정을 유지하고 연결된 issue에 변경을 기록합니다. 협업자가 추가되면 필수
승인 리뷰 수를 다시 검토합니다.

GitHub의 [ruleset에서 사용할 수 있는 규칙 안내](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)에서
각 규칙이 적용되는 방식을 확인할 수 있습니다.
