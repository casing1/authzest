export type Language = "en" | "ko";
export type Health = "checking" | "online" | "offline";
export type Failure = {
  stage: string | null;
  code: string | null;
  turn_start: string | null;
};
export type Phase = {
  candidate: string | null;
  status: string | null;
  test_exit_code: number | null;
  regression_status?: string | null;
  response_status?: number | null;
  cleanup_confirmed: boolean | null;
  generated_runtime_attempted: boolean | null;
  application_sha256: string | null;
  test_sha256: string | null;
  failure: Failure | null;
  transport_failure: Failure | null;
  comparison: {
    expected_profile: string | null;
    comparison_status: string | null;
    matches_expected_profile: boolean | null;
    case_count: number;
    matching_case_count: number;
    intended_match_count?: number | null;
    request_count: number;
    matching_request_count: number;
  } | null;
};
export type WorkflowView = {
  schema_version: "1.0";
  kind: "authzest-workflow-view";
  record_kind?: "owner-read-suggestion";
  record_version: "1.0" | "legacy-unversioned";
  provenance: "imported-unverified";
  assessment: {
    status: string;
    rationale: string;
    assumptions: string[];
    uncertainties: string[];
    limitations: string[];
  } | null;
  summary: {
    status: string | null;
    exit_code: number | null;
    proposal_status: string | null;
    execution_status: string | null;
    patch_application: string | null;
    applied: boolean | null;
    current_copy_state: string | null;
    restoration_status: string | null;
    recovery_required?: boolean | null;
    original_checkout_modified: boolean | null;
  };
  source_evidence: {
    scenario_id: string;
    source: { path: string; sha256: string; text: string };
    declarations: unknown[];
    policy: string[];
    policy_authorship: string;
    policy_review: string;
  } | null;
  proposal: {
    rationale: string;
    assumptions: string[];
    uncertainties: string[];
    limitations: string[];
    after_source: { path: string; sha256: string | null; text: string };
    test: { path: string; sha256: string | null; text: string };
    changes: {
      path: string;
      before_sha256: string | null;
      after_sha256: string;
      diff: string;
    }[];
  } | null;
  session: {
    status: string | null;
    stopped_stage: string | null;
    closed: boolean | null;
    close_status: string | null;
    runtime_input_cleanup: string | null;
    cleanup_unconfirmed: boolean | null;
    clock_unconfirmed: boolean | null;
    workspace_state: string | null;
    stages: {
      stage: string;
      status: string | null;
      decision: string | null;
      expired: boolean | null;
      attempted: boolean | null;
      dispatched: boolean | null;
      reason: string | null;
    }[];
    checks: { before: Phase | null; after: Phase | null };
    authorization_status: string | null;
    verified_fix: boolean | null;
    isolation_established: boolean | null;
    resource_enforcement_established: boolean | null;
    test_report_authenticity: string | null;
  } | null;
  failure: Failure | null;
  availability: {
    before_source: boolean;
    declarations: boolean;
    raw_phase_captures: false;
  };
  warnings: string[];
};
