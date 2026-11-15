<p align="center">
  <a href="../../../development/GENERATED_REPAIR_IMAGES.md">English</a> ·
  <strong>한국어</strong>
</p>

# 생성 수정 이미지 — 빌드한 이미지가 아닌 고정 입력

[문서 목록](../INDEX.md) · [Guest 진입점](GENERATED_REPAIR_GUESTS.md) ·
[런타임 메타데이터](GENERATED_REPAIR_PREFLIGHT.md)

## 범위 — 2026-11-15 KST

이 [#152](https://github.com/casing1/authzest/issues/152) 부분 기반은 분리된 T/테스트, A/애플리케이션,
B/relay 역할의 이미지 후보 입력을 기록합니다. 오프라인 입력 검사기를 추가하며 이미지 빌더·설치기나
활성 생성 코드 실행기는 추가하지 않습니다. #152는 열린 상태입니다. Manifest의
`status: "candidate-not-built"`, `image_ids: null`, `contents_verified: false`를 유지하며 입력 일치로
준비된 이미지나 살아 있는 profile을 만들어내지 않습니다.

이번 변경에는 build·pull·load·base layer 가져오기·컨테이너 생성/시작·생성 코드 실행·AI 호출이 없습니다.
새 공개 AuthZest 명령·런타임 결정·릴리스도 추가하지 않습니다.

## 기록한 후보 입력

소스의 [runtime/generated_repair/images](../../../../runtime/generated_repair/images/)에는
[manifest](../../../../runtime/generated_repair/images/manifest.json) 하나, platform/역할별 dependency
lock 6개, Dockerfile recipe 6개, 보존한 원본 base-image JSON 5개가 있습니다. 후보 base는
`docker.io/library/python:3.12.16-slim-bookworm`이며 recipe는 변경 가능한 tag가 아니라 각 platform의
기록한 child manifest digest를 사용합니다.

| 역할 | platform별 추가 고정 wheel | 의도한 역할                                         |
| ---- | -------------------------- | --------------------------------------------------- |
| T    | 20                         | FastAPI 애플리케이션과 생성 pytest 테스트           |
| A    | 14                         | 고정 guest launcher가 제공하는 FastAPI 애플리케이션 |
| B    | 0                          | base Python 표준 라이브러리를 사용하는 관리형 relay |

`linux/amd64`, `linux/arm64` 모두 명시적 입력을 갖고 선택한 dependency 집합의 package 이름 합집합은
22개입니다. B가 wheel을 추가하지 않는다는 뜻이며 base OS·Python 설치·상속한 파일이 의존성이 없거나
검증됐다는 뜻은 아닙니다.

Guest 후보는 검토한 release metadata에서 `pytest==9.0.3`을 선택합니다. 호스트 개발 환경과 별개이며
기존 호스트 pytest 제약은 바꾸지 않습니다. 고정 guest launcher는 `-c /dev/null`과 정확한 테스트
선택을 유지합니다. 이미지 입력이 테스트 탐색을 확대하거나 모델이 선택한 의존성을 추가하거나
launcher 소스를 수정하지 않습니다.

## 오프라인 검사가 확인하는 범위

[scripts/generated_image_inputs.py](../../../../scripts/generated_image_inputs.py)는 닫힌 manifest,
역할/platform 집합, package metadata와 dependency 선택을 유지관리 소스와 대조합니다. 기록한 원본
OCI/Docker JSON 바이트는 선언한 index → 선택 child manifest → config digest 연결과 일치해야 합니다.
index는 선언한 Linux architecture/variant를 선택하며, 선택 config는 OS/architecture와 기록한 정확한 Python 환경 결합에 맞아야 합니다.
현재 guest 자산의 바이트, 해시 고정 lock 텍스트와 고정 Dockerfile recipe도 비교합니다.

이는 입력 식별자·일관성 검사입니다. 보존한 upstream 문서나 wheel 선언이 발행자를 인증하거나 서명을
검증하거나 공급망 출처를 입증하지 않습니다. 같은 기록 입력의 digest와 일치한다는 사실은 이미지 내부
파일의 독립적 증거가 아닙니다. Root filesystem layer나 완성한 이미지는 검사하지 않습니다.

향후 recipe는 저장소 checkout·사용자 파일·살아 있는 workspace 대신 선택한 `requirements.txt`,
`wheels/`, 고정 `assets/`만 있는 최소 준비 context를 기대합니다. T/A는 네트워크 비활성,
`--no-index`, `--no-deps`, `--require-hashes`를 사용하는 wheel 전용 설치를 기술하며 B는 package를
설치하지 않습니다. 검사 중 Dockerfile 지시는 비활성 텍스트이고 flag는 관찰한 빌드 격리·런타임 제약이
아닙니다. Context 준비·검토한 build/provisioning·결과 로컬 image ID 검증은 별도 작업입니다.

## 개발 checkout에서 검사

소스 개발 환경을 설치한 뒤 다음을 실행합니다.

```bash
python -m scripts.generated_image_inputs --check
```

기본 동작도 같은 오프라인 검사입니다. 로컬 후보 입력을 읽어 JSON 요약을 출력하며 wheel 다운로드·
registry/Engine 접속·Dockerfile 실행·wheel 코드 import는 하지 않습니다. 성공 요약도 빌드하지 않은
후보를 설명할 뿐 실행 권한을 부여하지 않습니다.

선택적 Python API `verify_wheelhouse(root, wheelhouse, role, platform)`는 명시적으로 제공한 기존 wheel
디렉터리를 받습니다. 정확한 선택 파일 이름, 제한된 일반 파일 바이트·크기/digest, 비활성 wheel ZIP
metadata를 검사하며 다운로드·설치·import는 하지 않습니다. 이 추가 바이트 관찰도 서명·이미지 내부
내용·비트 단위 재현 빌드·효과적 resource 제약·검증된 수정을 입증하지 않습니다.

## 분리된 Engine bootstrap과 남은 조건

비공개 [Engine metadata bootstrap](GENERATED_REPAIR_PREFLIGHT.md)은 이미지 ID나 기대 daemon
식별자를 만들어내지 않고 version/info 관찰을 표현합니다. `/version`과 고정 `/v1.51/info`만 사용하며
광고한 API 범위가 미지원이면 두 번째 요청 전에 거부합니다. Engine 식별자는 관찰했지만 고정하지 않은
상태이고 전체 runtime profile 생성·이미지 검사·executor 활성화는 하지 않습니다. 공개 CLI 흐름도
아닙니다.

생성 실행 전에는 검토한 이미지 준비/내용·로컬 image ID, 효과적 정지 컨테이너 검사, 현재 입력/세션
결정, 제한된 실행/수집·정확한 guest 정리 확인이 필요합니다. 이후 설치형 before/after/restore 수용과
로컬 결과 UI도 남아 있습니다. `ready`·실행 권한·수정 검증은 성립하지 않습니다. #89 위험 수용·#152
완료·버전 변경·릴리스 권한은 이 문서에 포함하지 않습니다.
