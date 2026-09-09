[English template](https://github.com/casing1/authzest/blob/main/.github/pull_request_template.md) ·
[문서 목차](INDEX.ko.md)

# Pull request 작성 안내

GitHub는 `.github/pull_request_template.md`의 영어 템플릿을 기본으로 불러옵니다. 아래 내용은 같은
항목을 한국어로 설명한 작성 안내입니다. 자세한 작업 흐름은 [기여 안내](CONTRIBUTING.ko.md)를
따릅니다. issue를 닫는 `Closes #`와 검사 이름은 번역하지 않습니다.

## 변경 요약

<!-- 무엇을 왜 바꿨으며, 이 범위가 검토 가능한 최소 단위인 이유를 적습니다. -->

## 연결된 issue

Closes #

## 검증

<!-- 실행한 정확한 검사와 수동 확인 시나리오를 적습니다. -->

- [ ] Python 테스트
- [ ] Python lint와 format 검사
- [ ] 관련 변경의 frontend lint, format, build
- [ ] 관련 변경의 CLI 또는 바이너리 smoke test

## 보안과 호환성

<!-- 보안 영향, 새로운 신뢰 경계, 외부 프로세스 또는 네트워크 접근을 설명합니다. 해당하지 않으면 "없음"으로 적습니다. -->

## 체크리스트

- [ ] 변경 목적이 하나로 명확하며 issue의 완료 조건을 충족했습니다.
- [ ] 커밋은 의미 있는 변경 단위이며, 가능하면 기능과 해당 테스트를 함께 포함했습니다.
- [ ] 새 동작 또는 수정된 동작에 테스트가 있거나, 문서만 변경해 테스트가 해당하지 않습니다.
- [ ] finding이 있다면 소스 근거를 포함하고 unknown과 vulnerable을 구분했습니다.
- [ ] 비밀키, 개인정보, 빌드 결과물 또는 관련 없는 변경을 포함하지 않았습니다.
- [ ] 필요한 경우 사용자에게 보이는 동작과 한계를 README 외의 문서에 기록했습니다.
- [ ] 영어 문서와 한국어 번역을 함께 갱신했습니다. 프로젝트 README 변경에는 일본어와 러시아어
      번역도 반영했습니다.
- [ ] 새 안내 문서에 원본·번역 간 언어 링크를 넣고 영어와 한국어 문서 목차에 등록했습니다.
- [ ] merge commit으로 병합하기 전에 필수 `python`, `frontend`, `CodeQL` 검사를 통과했습니다.
