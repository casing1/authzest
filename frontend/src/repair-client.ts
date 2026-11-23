import type { RepairDiagnostics, RepairRun } from "./repair-types.js";
import { repairStages } from "./repair-types.js";

type BrowserLocation = Pick<Location, "hash" | "pathname" | "search">;
type BrowserHistory = Pick<History, "replaceState">;

export function takeRepairLaunchToken(
  location: BrowserLocation,
  history: BrowserHistory,
): string | null {
  const params = new URLSearchParams(location.hash.slice(1));
  const values = params.getAll("authzest-ai");
  if (!values.length) return null;
  params.delete("authzest-ai");
  const remaining = params.toString();
  // Capture once before React mounts: StrictMode can call state initializers twice.
  try {
    history.replaceState(
      null,
      "",
      location.pathname + location.search + (remaining ? `#${remaining}` : ""),
    );
  } catch {
    return null;
  }
  return values.length === 1 && /^[A-Za-z0-9_-]{43}$/.test(values[0])
    ? values[0]
    : null;
}

export class RepairAPIError extends Error {
  readonly status: number;
  constructor(status = 0) {
    super("The local AI workflow request failed.");
    this.status = status;
  }
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function boundedText(value: unknown, limit = 128): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= limit;
}
function identity(value: unknown): value is string {
  return boundedText(value) && /^[A-Za-z0-9_-]+$/.test(value);
}
function integer(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}

export function isRepairRun(value: unknown): value is RepairRun {
  if (
    !object(value) ||
    !identity(value.run_id) ||
    !integer(value.revision) ||
    !["running", "waiting", "stopping", "finished", "failed"].includes(
      String(value.state),
    ) ||
    !Array.isArray(value.events) ||
    value.events.length > 256 ||
    !value.events.every(
      (row) =>
        object(row) &&
        integer(row.sequence) &&
        boundedText(row.stage) &&
        boundedText(row.status),
    ) ||
    typeof value.result_available !== "boolean" ||
    typeof value.cancel_requested !== "boolean" ||
    !(value.failure === null || boundedText(value.failure, 512)) ||
    !(value.view_error === null || boundedText(value.view_error, 512))
  )
    return false;
  if (value.pending !== null) {
    const p = value.pending;
    if (
      !object(p) ||
      !identity(p.prompt_id) ||
      !repairStages.includes(p.stage as (typeof repairStages)[number]) ||
      !boundedText(p.prompt, 2048) ||
      !object(p.plan) ||
      typeof p.remaining_seconds !== "number" ||
      !Number.isFinite(p.remaining_seconds) ||
      p.remaining_seconds < 0 ||
      p.remaining_seconds > 300
    )
      return false;
  }
  if (
    value.view !== null &&
    (!object(value.view) ||
      value.view.kind !== "authzest-workflow-view" ||
      value.view.schema_version !== "1.0" ||
      value.view.provenance !== "imported-unverified" ||
      !object(value.view.summary) ||
      !object(value.view.availability) ||
      !Array.isArray(value.view.warnings))
  )
    return false;
  return true;
}

async function request(
  path: string,
  token: string,
  signal?: AbortSignal,
  body?: unknown,
): Promise<Response> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "X-AuthZest-Token": token,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    referrerPolicy: "no-referrer",
  });
  if (!response.ok) throw new RepairAPIError(response.status);
  return response;
}

async function runResponse(response: Response): Promise<RepairRun> {
  const value: unknown = await response.json();
  if (!isRepairRun(value)) throw new RepairAPIError();
  return value;
}
function runPath(runID: string): string {
  if (!identity(runID)) throw new RepairAPIError();
  return `/api/ai/runs/${encodeURIComponent(runID)}`;
}
export async function getRepairSession(
  token: string,
  signal?: AbortSignal,
): Promise<RepairRun | null> {
  const value: unknown = await (
    await request("/api/ai/session", token, signal)
  ).json();
  if (!object(value) || !(value.run === null || isRepairRun(value.run)))
    throw new RepairAPIError();
  return value.run;
}
export async function startRepair(
  token: string,
  model: string,
  signal?: AbortSignal,
): Promise<RepairRun> {
  return runResponse(
    await request("/api/ai/runs", token, signal, {
      model,
      timeout_seconds: 120,
    }),
  );
}
export async function decideRepair(
  token: string,
  runID: string,
  promptID: string,
  answer: string,
  signal?: AbortSignal,
): Promise<RepairRun> {
  return runResponse(
    await request(`${runPath(runID)}/decisions`, token, signal, {
      prompt_id: promptID,
      answer,
    }),
  );
}
export async function cancelRepair(
  token: string,
  runID: string,
  signal?: AbortSignal,
): Promise<RepairRun> {
  return runResponse(
    await request(`${runPath(runID)}/cancel`, token, signal, {}),
  );
}
export async function inspectRepairAccount(
  token: string,
  signal?: AbortSignal,
): Promise<RepairDiagnostics> {
  const value: unknown = await (
    await request("/api/ai/diagnostics", token, signal, {})
  ).json();
  if (
    !object(value) ||
    !["authenticated", "unauthenticated", "unavailable", "unknown"].includes(
      String(value.codex_status),
    ) ||
    !["supported", "unsupported", "unknown"].includes(
      String(value.version_status),
    ) ||
    value.model_access !== "not-checked"
  )
    throw new RepairAPIError();
  return {
    codex_status: value.codex_status as RepairDiagnostics["codex_status"],
    version_status: value.version_status as RepairDiagnostics["version_status"],
    model_access: "not-checked",
  };
}
export async function downloadRepairResult(
  token: string,
  runID: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await request(`${runPath(runID)}/result`, token, signal);
  if (
    response.headers.get("content-type")?.split(";", 1)[0] !==
    "application/json"
  )
    throw new RepairAPIError();
  const blob = await response.blob();
  if (blob.size > 4 * 1024 * 1024) throw new RepairAPIError();
  return blob;
}
