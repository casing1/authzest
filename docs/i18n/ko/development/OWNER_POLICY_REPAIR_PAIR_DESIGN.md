<p align="center">
  <a href="../../../development/OWNER_POLICY_REPAIR_PAIR_DESIGN.md">English</a> ·
  <strong>한국어</strong>
</p>

# 합성 소유자 정책 repair pair — 검토용 설계

[문서 인덱스](../INDEX.md) · [개발 계획](DEVELOPMENT_PLAN.md) ·
[구현된 S1 API](../reference/OWNER_POLICY_RECOMMENDATION.md) ·
[이슈 #81](https://github.com/casing1/authzest/issues/81)

## 상태 및 요청하는 결정

**제안 상태이며 미등록·미실행 — 2026-10-16 KST.** 이 문서는 의도적으로 잘못된 **테스트 전용**
정책 하나와 그 정확한 수정본, 그리고 어시스턴트가 작성한 예상 라벨 8개를 제안합니다.
소스 변형, 레지스트리 항목, 모델 요청, 실행 가능한 케이스, worker, CLI 또는 애플리케이션 기능은
추가하지 않습니다. 문서/CI 성공은 시나리오 검토, 라벨 승인 또는 실행 근거가 아닙니다.

기준선: main `7173a54d12f50605b5f5e4d4388d350fd6df276d`. S1은
[PR #99](https://github.com/casing1/authzest/pull/99)를 통해 `4290d2d`에서 제공되었으며,
여전히 레지스트리 `empty-v1`에서 `no-change`와 `unknown`만 허용합니다. 이 제안은 S1이나
과거의 [원래 설계](OWNER_POLICY_IMPROVEMENT_DESIGN.md)를 수정하지 않습니다.

다음 관리자의 결정은 후속 오프라인 레지스트리/diff 미리보기 구현을 위해 **이 정확한 합성
시나리오, 소스 쌍 및 예상 라벨 8개**를 수용할지 여부입니다. 이 결정은 명시되지 않은 향후 스키마,
소스 공유, 유료 리뷰, 정책 실행, 파일 적용, 복구, 병합 또는 출판을 승인하지 않습니다.
바이트/케이스가 변경되면 새 검토가 필요하며, 이 검토 전에 구현에서 잘못된 변형을 등록해서는
안 됩니다. #81과 #35는 아직 완료되지 않았습니다.

## 프로덕션 취약점이 아닌, 소유한 회귀 시나리오 하나

유지·관리 중인 판정 함수는 신뢰할 수 있는 인증, 리터럴 `reports:read`, 정확한 subject/owner
일치를 올바르게 요구합니다. `examples/fastapi_owner_policy/policy.py`나 `OWNER_POLICY_SOURCE`를
변경하거나 취약하다고 설명하지 마세요. 제안하는 부정 fixture는 인증, scope 및 입력 검사를
유지하면서 마지막 소유권 비교만 의도적으로 생략합니다. 올바르게 유지·관리되는 소스가 수정된
대조군입니다.

입력은 HTTP claim이 아닌 로컬 합성 신뢰 컨텍스트입니다. dataclass를 생성하는 것만으로는
아무것도 인증되지 않으며, 보고서 식별자/소유권에는 신뢰할 수 있는 조회가 필요합니다. HTTP,
인증 제공자, 라우터, 데이터베이스, 네트워크 대상 또는 실제 사용자 데이터는 포함되지 않습니다.
이는 정책 수준의 방어적 회귀 시나리오이며 exploit 스크립트나 엔드포인트 인가 테스트가 아닙니다.
올바른 정책에 대한 `no-change`/`unknown`은 여전히 유효하며, 패치를 생성하는 것이 성공 기준은
아닙니다.

## 정확한 후보 바이트

고정된 기준선의 전체 `OWNER_POLICY_SOURCE` 리터럴을 **after** 바이트로 사용합니다. 이는 해당
기준선에서 유지·관리되는 예제 파일과 바이트 단위로 동일합니다. 두 후보 모두 BOM 없는 UTF-8,
LF 전용이며 마지막 LF를 유지합니다. 개행, 들여쓰기 또는 식별자 정규화는 허용되지 않습니다.

메모리에서 정확히 한 줄인
`    return subject == owner_id and "reports:read" in scopes`를
`    return "reports:read" in scopes`로 바꾸되 해당 LF를 유지한 뒤, 맨 앞에 정확히 다음 줄과
LF 하나를 붙여 **before**를 도출합니다.

```text
# INTENTIONALLY INCORRECT TEST-ONLY: ownership comparison deliberately omitted.
```

그 외 바이트는 변경하지 않습니다. 정확한 수정은 해당 경고를 제거하고 동등성 절을 복원하며,
기존 모듈 docstring의 첫 줄은 변경하지 않습니다. 논리적 파일명 `policy.py`는 표시용 데이터이며,
기존 checkout에 대한 쓰기 대상이 아닙니다.

| 스냅샷 | UTF-8 바이트 | SHA-256                                                            |
| ------ | ------------ | ------------------------------------------------------------------ |
| before | 2,016        | `54f36634f471d9f603218aafb379ac1d082c38e94b08284549d0311e910cf950` |
| after  | 1,960        | `faf39b33515a658e92e61a51c69e1a437eb3dc0dcf8511ef806558d30ee36f04` |

다음은 정확한 내용을 보여 주는 예시 diff입니다. 향후 host 코드는 등록된 바이트에서 자체적으로
전체 diff를 도출하며, 모델이 제공한 diff를 신뢰하지 않습니다.

```diff
--- a/policy.py
+++ b/policy.py
@@ -1,2 +1,1 @@
-# INTENTIONALLY INCORRECT TEST-ONLY: ownership comparison deliberately omitted.
 """Pure policy for a maintained synthetic example, not an authentication provider.
@@ -51,4 +50,4 @@
         return False
     if not all(_nonblank_string(scope) for scope in scopes):
         return False
-    return "reports:read" in scopes
+    return subject == owner_id and "reports:read" in scopes
```

제안하는 시나리오 이름은 `synthetic-owner-omission-v1`이며, 수용된 레지스트리 ID나 승인
자격 증명이 아닙니다. 구현은 host가 도출한 pair ID를 전체 버전 지정 manifest에 결합해야 합니다.
여기에는 두 전체 소스 텍스트/해시, 논리적 경로, 정확한 S1 정책 전용 기준과 신뢰 입력 가정,
시나리오 및 전체 케이스/라벨 데이터가 포함됩니다. 사람이 읽기 쉬운 slug, after 해시 또는 복사한
미리보기만으로 pair를 식별하지 마세요. 내용/버전이 변경되면 관련 binding은 무효화됩니다.

## 제안하는 케이스 및 라벨 8개

이는 **어시스턴트가 작성했으며 아직 검토되지 않은** 데이터입니다. 새로운 AI 출력, 유지·관리되는
평가셋 또는 이전에 승인된 #77 라벨이 아닙니다. 새로운 정확한 세트로 검토해야 합니다. `expected`는
정책 기준이며, 의도적으로 잘못된 후보에 맞추어 변경하지 않습니다. scope 배열은 고정 harness가
지원하는 `frozenset`으로 디코딩하며, 임의 객체나 실행 가능한 표현식으로 바꾸지 않습니다.

```json
[
  {
    "case_id": "owner-control",
    "principal": {
      "subject": "alice",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "allow"
  },
  {
    "case_id": "non-owner",
    "principal": {
      "subject": "bob",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "missing-read-scope",
    "principal": { "subject": "alice", "authenticated": true, "scopes": [] },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "unauthenticated-owner",
    "principal": {
      "subject": "alice",
      "authenticated": false,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "missing-principal",
    "principal": null,
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "missing-report",
    "principal": {
      "subject": "alice",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": null,
    "expected": "deny"
  },
  {
    "case_id": "wildcard-is-not-read",
    "principal": {
      "subject": "alice",
      "authenticated": true,
      "scopes": ["reports:*"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  },
  {
    "case_id": "exact-owner-no-normalization",
    "principal": {
      "subject": " alice",
      "authenticated": true,
      "scopes": ["reports:read"]
    },
    "report": { "report_id": "report-001", "owner_id": "alice" },
    "expected": "deny"
  }
]
```

제안하는 세트는 allow 라벨 1개와 deny 라벨 7개로 구성됩니다. 정적 추론으로는 **deny 케이스
2개**인 `non-owner`와 `exact-owner-no-normalization`이 before에서는 잘못 허용되고 after에서는
거부될 것으로 예측합니다. 긍정 대조군 `owner-control`은 양쪽에서 모두 허용되고, 나머지 대조군
5개는 양쪽에서 모두 거부될 것으로 예측합니다. 이는 관찰이 아닌 가설입니다. subject의
`" alice"`에 있는 앞쪽 공백은 의미가 있으며, owner는 정확히 `"alice"`입니다.

위의 정확한 8개 원소 배열의 canonical SHA-256은
`96f3c7bc3f88c0edc617ed64f047fbfeb95973c36cad100b49534a8f8bfadfa3`입니다.
UTF-8 JSON, 재귀적으로 정렬한 객체 키, 압축 구분자, 배열 순서 유지, 마지막 LF 없음을 기준으로
합니다. 이 내용 식별값은 제안한 예상 라벨을 포함하지만 라벨 검토 증표는 아닙니다.

모든 케이스의 실제 before/after 관찰은 현재 **null / not-run**이고, 비교는 평가되지 않았으며,
인가 상태는 unknown으로 유지됩니다. 추후 8개가 모두 일치하더라도 이 유한한 합성 정책 회귀
시나리오만 뒷받침할 뿐, 보안 증명이나 HTTP 강제를 의미하지 않습니다. 원래 모델 케이스 10개,
#77 검토/관찰 기록 또는 별도의 개발자 테스트 라벨 28개를 덮어쓰지 마세요.

## 후속 구현 경계

1. **오프라인 레지스트리와 미리보기 우선.** 정확한 설계/라벨 검토 후, 이 등록 pair 및 host가
   도출하는 단일 파일 diff를 위한 별도의 버전 지정 폐쇄형 계약을 구현합니다. S1 스키마
   `1.0`/`empty-v1`, 기존 payload의 수용/거부 및 모든 과거 식별값을 보존합니다. 전체 산출물과
   최종 미리보기 예산을 다시 검증하며, ID와 dataclass는 승인 권한이 아닙니다.
2. **Codex 통합은 별도 진행.** 연결하기 전에 정확히 최소화한 요청/출력 스키마와 prompt를
   검토합니다. 기존 공유 결정을 재사용하지 않습니다. 추후 호출에는 새롭고 완전한 공유 미리보기,
   계정/모델/사용량/시간 제한 및 명시적 승인이 필요합니다. 모델의 케이스 제안은 예상값을 별도로
   검토하는 제한된 JSON 데이터로 유지하며, 모델 텍스트를 소스, shell, 명령, import 또는
   신뢰할 수 있는 승인/상태로 사용하지 않습니다. 첫 수정은 등록된 템플릿의 선택이며,
   임의의 AI 생성 코드나 독립적으로 발견한 프로덕션 결함이 아닙니다.
3. **전용 고정 검사 recipe.** #80은 올바른 정책과 해당 worker를 고정하므로 잘못된 소스를
   거부해야 합니다. 소스 해시 범위를 넓히거나 호출자가 선택한 경로/텍스트를 허용하지 마세요.
   별도로 검토한 worker/recipe는 pair, 정확한 구현/worker 식별값, 케이스/라벨 세트, 전송 규약,
   제한 및 정리 동작을 고정해야 합니다. 이 설계의 fence나 AI가 작성한 테스트를 실행하지 마세요.
4. **새 복사본에만 적용.** 기존 `FixtureApplySession`은 `main.py`용이며, 일반적인 proposal
   검사가 이 pair의 등록을 증명하지는 않습니다. 새 파일명만 허용하거나 이를 debug/설정 상태
   검사기에 억지로 맞추지 마세요. 현재 before/after 바이트, workspace/파일 식별값 및 정확한
   host diff를 가진 pair-bound 단일 파일 `policy.py` coordinator를 설계합니다. 원본, 이후
   사용자 편집 및 실패/복구 기록을 보존합니다. 현재 지원 범위가 기존 checkout, 다중 파일,
   Windows 적용 또는 재시작/재개 지원을 의미하지는 않습니다.

소스 공유, 정확한 라벨 검토, before 검사, 정확한 diff 승인, 적용, after 검사 및 복구는 각각
별도의 현재 상태 기반 결정입니다. 완료된 before 검사는 after 검사를 승인하거나 패치 적용을
증명할 수 없습니다. 유효한 미리보기나 diff 적용을 검증 완료로 간주해서는 안 됩니다. 시간 초과,
취소, 오래되거나 거부/만료/재사용된 결정, 변경된 worker/케이스/소스 및 이후 사용자 편집은
실패 시 거부합니다. unknown 관찰, 불완전한 정리, journal/fsync 실패 및 불확실한 복구는
unknown/failed로 유지하며, 조용히 통과시키지 않습니다. 자동 재시도나 자동 복구는 없습니다.
자식 프로세스는 OS/네트워크 sandbox가 아니며, 신뢰할 수 있는 도구와 같은 사용자 권한의 악의적인
동시 writer가 없다는 점은 여전히 가정입니다.

## 검토 및 전달 체크리스트

- [ ] 관리자가 이 정확한 시나리오와 전체 before/after 바이트, 해시 및 경고를 검토합니다.
- [ ] 관리자가 예상 라벨 8개 모두를 하나의 정확한 세트로 별도 승인하거나 수정합니다.
- [ ] 다음 단계를 구현하기 전에 폐쇄형 오프라인 pair/미리보기 스키마를 검토합니다.
- [ ] 구현 시 오프라인 긍정/거부/오래된 상태/위조/예산 및 부수 효과 방지 테스트를 추가합니다.
- [ ] provider 공유, 고정 실행 recipe 및 복사/적용/검사/복구 설계를 별도로 검토합니다.
- [ ] 정확한 계획이 마련되었을 때만 새롭고 제한된 live/runtime 승인을 받습니다.

설계 전용 PR에서는 이 체크리스트를 미체크 상태로 유지합니다. casing1, 관련 기존 라벨 및
마일스톤 04를 지정하고, 관리자 검토를 기다리는 동안 draft 상태를 사용합니다. 일반 CI는
수동 유료 리뷰, 자동 리뷰 활성화 또는 병합을 승인하지 않습니다. #81/#35/#82의 수용 기준과
#89/#83의 잔여 도구/출판 gate를 독립적으로 유지하며, 여기서는 버전, tag 또는 release를
변경하지 않습니다.
