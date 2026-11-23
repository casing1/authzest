import type { WorkflowView } from "./viewer-types.js";

export const repairStages = [
  "runtime",
  "share",
  "copy",
  "before",
  "diff",
  "apply",
  "after",
  "restore",
] as const;
export type RepairStage = (typeof repairStages)[number];
export type RepairEvent = { sequence: number; stage: string; status: string };
export type RepairPending = {
  prompt_id: string;
  stage: RepairStage;
  prompt: string;
  plan: Record<string, unknown>;
  remaining_seconds: number;
};
export type RepairRun = {
  run_id: string;
  revision: number;
  state: "running" | "waiting" | "stopping" | "finished" | "failed";
  events: RepairEvent[];
  pending: RepairPending | null;
  view: WorkflowView | null;
  view_error: string | null;
  result_available: boolean;
  failure: string | null;
  cancel_requested: boolean;
};
export type RepairDiagnostics = {
  codex_status: "authenticated" | "unauthenticated" | "unavailable" | "unknown";
  version_status: "supported" | "unsupported" | "unknown";
  model_access: "not-checked";
};

export function activeRepair(run: RepairRun | null): boolean {
  return run !== null && !["finished", "failed"].includes(run.state);
}
