<p align="center">
  <a href="../../../guides/PROPOSAL_PREVIEW.md">English</a> ·
  <strong>한국어</strong>
</p>

# 오프라인 제안·예상 결과 미리보기

[문서 목차](../INDEX.md) · [예상 결과 계약](../reference/EXPECTATION_CONTRACT.md)

## 범위와 버전

[#63](https://github.com/casing1/authzest/issues/63)은 alpha.3 이후 `authzest proposal-preview`를 추가합니다.
이 변경이 포함된 editable 소스 checkout을 사용하세요. 공개 alpha.3 바이너리에는 이 명령이 없습니다.
패키지 버전 `0.1.0a3`, 리포트 스키마 `1.2`와 기존 제안·예상 결과 스키마는 그대로입니다.
#35의 표시 단계이며 승인·실행 흐름 전체를 완료하는 것은 아닙니다.

명령은 명시적으로 선택한 JSON bundle 하나를 읽고 요청·검토·제안·예상 결과 manifest를 다시 검증한 뒤
연결된 근거, 정확한 diff, 이유, 예상 결과와 한계를 표시합니다. bundle 내부 경로를 읽거나 Git·현재
소스 파일을 확인하지 않고 Codex 호출, 패치 승인·적용, 테스트 생성·실행도 하지 않습니다.
기존 `codex-fixture` 산출물은 이 입력 형식이 아니며 해당 흐름의 실제 입력 공유·실행 경계는 그대로입니다.

## 재현 가능한 오프라인 데모

지원하는 POSIX 시스템에서 [개발 환경](../README.md#개발-환경)을 활성화하고 저장소 루트에서 실행합니다.

```bash
preview_dir=$(mktemp -d)
python -m scripts.demo_preview --output "$preview_dir/bundle.json"
authzest proposal-preview "$preview_dir/bundle.json"
authzest proposal-preview "$preview_dir/bundle.json" --json
```

내보내기 스크립트는 기존 공개 의도 개발 fixture인
`tests/fixtures/ai_evaluation/v1/public/main.py`만 읽고 애플리케이션 코드를 import하지 않고 목록화합니다.
호출자가 작성한 정책, 고정 응답의 `unknown` 검토, 무해한 주석만 추가하는 제안과 공개 의도 예상 결과를
묶습니다. 실제 모델 결과나 보안 수정이 아닙니다. 고정한 평가셋과 별도 평가 사례는 바꾸지 않습니다.

`--output`은 새 파일만 만들며 기존 경로에 덮어쓰기를 거부합니다. 이 옵션이 없으면 bundle을 stdout에
출력합니다. 내보내기 스크립트는 명시적으로 선택한 출력에만 기록하며 제품의 미리보기 명령 자체는
읽기 전용입니다. 임시 디렉터리는 이후 확인할 수 있도록 남겨둡니다.

기본 화면은 제공된 근거와 예상 결과를 도출한 diff·한계와 함께 묶어 표시합니다. `--json`은 검증된
미리보기를 ASCII 이스케이프 JSON으로 반환합니다. 비신뢰 표시 문자열은 터미널 제어 문자로 해석하지
않고 이스케이프합니다. 출력은 로컬에 남지만 선택한 bundle의 소스·정책을 포함할 수 있으므로
공유하거나 로그로 리다이렉트하기 전에 내용을 검토하세요.

## Bundle 형식과 Python API

bundle 스키마 `1.0`은 정확히 `schema_version`, `request`, `review`, `proposal`, `manifest`만 받습니다.
뒤의 네 필드는 기존 계약의 중첩 JSON 객체이며 파일명이나 별도로 인코딩한 JSON 문자열이 아닙니다.
직렬화한 전체 bundle은 UTF-8 기준 256 KiB 이하여야 합니다. 기존의 엄격한 JSON 제한, 중복 키 거부와
중첩 계약 검사도 적용하므로 개별 산출물이 유효해도 합친 크기는 제한을 초과할 수 있습니다.

네 산출물이 이미 메모리에 있다면 다음과 같이 사용합니다.

```python
from authzest.codex.preview import (
    prepare_preview_bundle,
    preview_bundle,
    validate_preview_bundle,
)

bundle = prepare_preview_bundle(request, review, proposal, manifest)
validated = validate_preview_bundle(bundle.payload_json)
preview = preview_bundle(validated)
```

불변 `ValidatedPreviewBundle`은 정규화한 JSON을 저장하고 내용에 연결된 `bundle_id`를 제공합니다.
반환한 사전은 원본과 분리되며 미리보기 소비자는 wrapper만 신뢰하지 않고 bundle을 다시 검증합니다.
실질적인 산출물 내용이 바뀌면 식별값이 달라지거나 연결이 무효가 됩니다. 순수 API는 플랫폼에
독립적이며 파일시스템·프로세스·제공자·네트워크 I/O를 하지 않습니다.

미리보기는 요청 메타데이터, 검토 내용, 근거와 제안·manifest 식별값을 유지합니다. 상태는 항상
`draft`, 검증은 `not-run`, 적용은 `false`, 관찰값은 `null`, 인가 판정은 `unknown`입니다.
이는 제공된 스냅샷의 구조 검사이며 정책 승인, 의미상 정확성, 현재 디스크/Git 상태의 최신성이나
보안 수정 성공을 입증하지 않습니다. 정책 의도는 호출자의 해석이고 일반 DI·scope 선언은 강제 적용의
근거가 아닙니다. 이 bundle에 연결되거나 실행 권한을 부여하는 승인 기록은 없습니다.

## 파일 처리와 실패

CLI 파일 reader는 우선 `O_NOFOLLOW`와 `O_NONBLOCK`을 제공하는 POSIX 시스템을 지원합니다.
Windows를 포함한 미지원 시스템에서는 입력을 열기 전에 실패합니다. 이 제한은 스캔이나 순수 Python
API에는 적용하지 않습니다.

선택한 입력은 크기 제한 내의 일반 UTF-8 파일이어야 합니다. 마지막 경로 요소의 symlink, FIFO 등
특수 파일, 읽는 중 감지한 변경, 잘못된 UTF-8·JSON이나 산출물 연결 불일치는 종료 코드 `2`와 stderr
오류를 반환하고 stdout에는 부분 미리보기도 출력하지 않습니다. 상위 디렉터리의 symlink까지
거부하거나 적대적인 동시 작성자에 대해 스냅샷을 보장하지는 않습니다. 직접 관리하는 파일과
디렉터리를 사용하세요.
바이트 제한은 파일시스템 접근의 실제 소요 시간 제한을 뜻하지 않습니다.

검증 성공은 종료 코드 `0`이며 예상 결과가 실제로 통과했다는 뜻이 아닙니다. 승인·적용·실행·제공자
옵션은 추가하지 않습니다. 후속 승인·검증 연동은 자체 정확한 계획과 별도 검토한 경계가 필요합니다.

## 오프라인 검사

```bash
python -m pytest tests/test_preview_bundle.py tests/test_proposal_preview_cli.py
```

이 테스트는 실제 제공자를 호출하거나 제안한 애플리케이션 소스를 실행하지 않고 bundle 계약,
연결된 표시와 파일·입력 거부 사례를 확인합니다. 모델 품질·런타임 인가·공개 바이너리 인수 검증
결과가 아니며 이 소스 추가 자체가 릴리스를 뜻하지도 않습니다.
