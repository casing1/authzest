export const repairMessages = {
  en: {
    tab: "AI repair",
    title: "Review an AI-assisted repair.",
    eyebrow: "LOCAL OPERATOR WORKFLOW",
    intro:
      "Generate a defensive test and availability-rule change for the maintained FastAPI owner-read scenario, then review each copy, check, change and recovery step.",
    scope: "AI target · packaged owner / archived-note scenario",
    scopeNote:
      "The source and policy in the sharing plan define this run. Static workspace inventory is a separate view.",
    locked: "Active AI controls are disabled for this page.",
    launch:
      "Start the local server with a reviewed private runtime configuration, then open the complete AI workspace URL printed in your terminal.",
    launchNote:
      "The launch link is private. It unlocks this page in memory; refreshing requires reopening that link. Existing result imports remain available without it.",
    account: "Codex connection",
    accountCheck: "Check existing login",
    unchecked: "Not checked",
    authenticated: "Authenticated",
    unauthenticated: "Not authenticated",
    unavailable: "Codex unavailable",
    unknown: "Unknown",
    supported: "Supported",
    unsupported: "Unsupported",
    version: "CLI version compatibility",
    accountNote:
      "Uses the existing Codex ChatGPT login. Login metadata does not establish access to the selected model. If needed, complete codex login in your terminal and check again.",
    model: "Exact Codex model for a new run",
    start: "Prepare AI repair",
    startNote:
      "Preparing a run first displays its runtime plan. Sending source, creating a copy, execution and changes each wait for their own current decision.",
    checking: "Reading current local session…",
    waiting: "Waiting for your decision",
    running: "Working on the approved step",
    stopping: "Stop requested; waiting for the current step and cleanup",
    finished: "Run ended",
    failed: "Coordinator stopped with an unresolved failure",
    stage: "Current step",
    runtime: "Runtime review",
    share: "Source sharing",
    copy: "Private copy",
    before: "Before check",
    diff: "Exact diff review",
    apply: "Apply to copy",
    after: "After check",
    restore: "Restore original copy bytes",
    review: "Current decision",
    reviewNote:
      "Review the complete plan and artifacts, then enter the exact phrase shown below. One decision applies only to this displayed step.",
    fullPlan: "Complete current plan",
    runtimeDetails: "Reviewed local runtime",
    image: "Exact local image",
    platform: "Guest platform",
    network: "Guest network",
    phaseBudget: "Phase execution / cleanup seconds",
    source: "Original source",
    proposed: "Proposed replacement",
    test: "Generated defensive test / PoC",
    diffs: "Exact proposed changes",
    policy: "Declared policy",
    rationale: "Proposal rationale",
    confirmation: "Current confirmation phrase",
    answer: "Enter the exact current phrase",
    approve: "Submit this decision",
    decline: "Decline this step",
    remaining: "seconds remaining · approximate",
    expired:
      "The displayed decision has expired. No approval is submitted automatically.",
    stop: "Stop workflow",
    stopNote:
      "A stop request waits for bounded work and cleanup. An applied private copy can remain recovery-required. Declining the after check can offer a separate restore decision; stopping does not restore automatically.",
    activity: "Host activity",
    activityNote:
      "These are local workflow events, not a stream of model tokens or private Codex logs.",
    noActivity: "No run has started.",
    download: "Download result JSON",
    resultNote:
      "Save the final JSON before closing the server. It contains private local evidence; choose its destination in your browser.",
    viewUnavailable:
      "The result has no supported bounded display projection. Download the JSON to inspect the retained record.",
    connectedError:
      "The local connection failed. A submitted action may already have reached the server. Check the current session before deciding again.",
    authError:
      "This page cannot access the active workspace. Reopen the complete launch URL from the terminal on the configured address.",
    conflictError:
      "The current run or decision changed. Review the refreshed session before deciding again.",
    inputError:
      "The model or confirmation was rejected. Check the exact current value.",
    actionError:
      "The local request was rejected. Review the current session and retained outcome.",
    recovery: "Recovery remains required",
    recoveryNote:
      "Inspect the retained copy and final record. Earlier successful checks do not confirm restoration or cleanup.",
    workspace: "Local operator workspace",
    busy: "Submitting…",
  },
  ko: {
    tab: "AI 수정",
    title: "AI 수정 제안을 검토하고 실행합니다.",
    eyebrow: "로컬 작업 흐름",
    intro:
      "관리하는 FastAPI 소유자 조회 시나리오에서 방어적 테스트와 가용성 규칙 수정을 생성하고, 복사·검사·변경·복구를 한 단계씩 검토합니다.",
    scope: "AI 대상 · 패키지에 포함된 소유자 / 보관 기록 시나리오",
    scopeNote:
      "공유 계획에 표시되는 소스와 정책을 사용합니다. 정적 workspace 목록은 별도 화면에서 확인합니다.",
    locked: "이 페이지에서는 AI 실행 기능이 활성화되지 않았습니다.",
    launch:
      "검토한 비공개 런타임 설정으로 로컬 서버를 시작한 뒤 터미널에 표시된 AI 작업 공간 URL 전체를 여세요.",
    launchNote:
      "실행 링크는 비공개로 보관하세요. 접속 정보는 이 페이지의 메모리에서만 유지하며 새로고침하면 링크를 다시 열어야 합니다. 저장 결과 가져오기는 링크 없이도 사용할 수 있습니다.",
    account: "Codex 연결",
    accountCheck: "기존 로그인 확인",
    unchecked: "확인 전",
    authenticated: "인증됨",
    unauthenticated: "로그인 필요",
    unavailable: "Codex 사용 불가",
    unknown: "불명",
    supported: "지원됨",
    unsupported: "지원되지 않음",
    version: "CLI 버전 호환성",
    accountNote:
      "기존 Codex ChatGPT 로그인을 사용합니다. 로그인 정보만으로 선택한 모델의 사용 권한을 보장하지 않습니다. 필요하면 터미널에서 codex login을 완료한 뒤 다시 확인하세요.",
    model: "새 작업에 사용할 Codex 모델 식별자",
    start: "AI 수정 준비",
    startNote:
      "작업을 준비하면 먼저 런타임 계획을 표시합니다. 소스 전송·복사본 생성·검사·변경은 각각 현재 단계의 결정을 기다립니다.",
    checking: "현재 로컬 세션 확인 중…",
    waiting: "현재 단계의 결정을 기다리는 중",
    running: "승인한 단계 작업 중",
    stopping: "중단 요청됨 · 현재 작업과 정리 완료를 기다리는 중",
    finished: "작업 종료",
    failed: "해결되지 않은 오류로 조정 작업 종료",
    stage: "현재 단계",
    runtime: "런타임 검토",
    share: "소스 공유",
    copy: "비공개 복사본",
    before: "수정 전 검사",
    diff: "정확한 diff 검토",
    apply: "복사본에 적용",
    after: "수정 후 검사",
    restore: "복사본을 원래 바이트로 복구",
    review: "현재 결정",
    reviewNote:
      "전체 계획과 파일을 검토한 뒤 아래의 정확한 확인 문구를 입력하세요. 한 번의 결정은 표시된 현재 단계에만 적용됩니다.",
    fullPlan: "현재 전체 계획",
    runtimeDetails: "검토할 로컬 런타임",
    image: "정확한 로컬 이미지",
    platform: "Guest 플랫폼",
    network: "Guest 네트워크",
    phaseBudget: "단계 실행 / 정리 시간(초)",
    source: "원본 소스",
    proposed: "수정 제안 소스",
    test: "생성한 방어적 테스트 / PoC",
    diffs: "정확한 변경 제안",
    policy: "명시한 정책",
    rationale: "수정 제안 근거",
    confirmation: "현재 확인 문구",
    answer: "현재 문구를 정확히 입력",
    approve: "현재 결정 전달",
    decline: "현재 단계 거절",
    remaining: "초 남음 · 근사값",
    expired:
      "표시된 결정의 유효 시간이 지났습니다. 승인을 자동으로 제출하지 않습니다.",
    stop: "작업 중단",
    stopNote:
      "중단 요청은 현재 작업과 정리를 기다립니다. 적용한 비공개 복사본은 복구 필요 상태로 남을 수 있습니다. 수정 후 검사를 거절하면 별도의 복구 결정을 표시할 수 있으며, 중단만으로 자동 복구하지 않습니다.",
    activity: "로컬 작업 기록",
    activityNote:
      "호스트의 단계별 작업 기록입니다. 모델 토큰 스트림이나 비공개 Codex 원본 로그를 표시하지 않습니다.",
    noActivity: "시작한 작업이 없습니다.",
    download: "결과 JSON 다운로드",
    resultNote:
      "서버를 닫기 전에 최종 JSON을 저장하세요. 비공개 로컬 근거가 포함되며 브라우저에서 저장 위치를 선택합니다.",
    viewUnavailable:
      "지원하는 크기와 형식의 결과 화면을 만들 수 없습니다. JSON을 내려받아 보존된 기록을 확인하세요.",
    connectedError:
      "로컬 연결에 실패했습니다. 제출한 동작은 이미 서버에 전달됐을 수 있습니다. 현재 세션을 확인한 뒤 다시 결정하세요.",
    authError:
      "현재 페이지에서 활성 작업 공간에 접근할 수 없습니다. 터미널의 전체 실행 URL을 지정된 주소에서 다시 여세요.",
    conflictError:
      "현재 작업이나 결정이 바뀌었습니다. 갱신한 세션을 검토한 뒤 다시 결정하세요.",
    inputError:
      "모델이나 확인 문구를 거절했습니다. 정확한 현재 값을 확인하세요.",
    actionError:
      "로컬 요청을 거절했습니다. 현재 세션과 보존한 결과를 확인하세요.",
    recovery: "복구가 여전히 필요합니다",
    recoveryNote:
      "보존한 복사본과 최종 기록을 확인하세요. 앞선 검사 통과만으로 복구나 정리를 확인할 수는 없습니다.",
    workspace: "로컬 작업 공간",
    busy: "전달 중…",
  },
} as const;

export type RepairErrorText =
  | "connectedError"
  | "authError"
  | "conflictError"
  | "inputError"
  | "actionError";
