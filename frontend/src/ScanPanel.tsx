import { type FormEvent, useEffect, useRef, useState } from "react";

type Props = {
  language: "en" | "ko";
  health: "checking" | "online" | "offline";
};
type Route = {
  path: string;
  methods: string[];
  function: string;
  file: string;
  line: number;
  registration_id?: string | null;
};
type Diagnostic = {
  code: string;
  message: string;
  severity: "warning" | "error";
  location: { file: string; line: number | null; column: number | null };
};
type Report = {
  root: string;
  python_files: number;
  route_count: number;
  routes: Route[];
  parse_errors: string[];
  codex_status: string;
  schema_version?: string;
  analysis_status?: "bounded" | "partial";
  diagnostics?: Diagnostic[];
};

const copy = {
  en: {
    eyebrow: "STATIC ROUTE INVENTORY",
    title: "Inspect FastAPI source declarations",
    intro:
      "Collect supported route declarations without running the target. Unsupported declarations may be missing. This inventory does not establish authentication or authorization safety.",
    workspace: "Configured workspace",
    configured: "Workspace selected when authzest ui starts",
    analyze: "Analyze repository",
    scanning: "Scanning…",
    failed: "Scan failed",
    notScanned: "Not scanned",
    partial: "Partial inventory",
    bounded: "Bounded inventory",
    summary: "Analysis summary",
    overview: "ANALYSIS OVERVIEW",
    codex: "Codex analysis",
    files: "Python files",
    routes: "API routes",
    diagnostics: "Diagnostics",
    discovered: "Discovered routes",
    total: "total",
    disabled: "disabled",
    requestError:
      "The scan failed or returned an invalid report. Previous results have been cleared. Please try again.",
    emptyStart:
      "Analyze the configured workspace to collect route declarations.",
    emptyScanning:
      "Collecting source declarations from the configured workspace.",
    emptyPartial:
      "No routes were found within the supported scope. Check the unresolved declarations and diagnostics.",
    emptyBounded:
      "No routes were found within the supported scope. This does not establish that endpoints are absent or access controls are safe.",
    partialNotice:
      "Errors or unresolved declarations were found. These are partial results and do not represent every endpoint or establish access-control safety.",
    legacy: "Legacy parse errors",
  },
  ko: {
    eyebrow: "정적 라우트 목록",
    title: "FastAPI 소스 선언을 확인합니다",
    intro:
      "대상 코드를 실행하지 않고 지원하는 라우트 선언을 수집합니다. 지원하지 않는 선언은 빠질 수 있으며, 이 목록은 인증·인가의 안전성을 보장하지 않습니다.",
    workspace: "설정된 작업 공간",
    configured: "authzest ui 시작 시 선택한 작업 공간",
    analyze: "저장소 분석",
    scanning: "분석 중…",
    failed: "분석 실패",
    notScanned: "분석 전",
    partial: "부분 목록",
    bounded: "지원 범위 내 목록",
    summary: "분석 요약",
    overview: "분석 개요",
    codex: "Codex 분석",
    files: "Python 파일",
    routes: "API 라우트",
    diagnostics: "진단",
    discovered: "발견된 라우트",
    total: "개",
    disabled: "비활성화",
    requestError:
      "분석에 실패했거나 올바르지 않은 결과를 받았습니다. 이전 결과는 지웠습니다. 다시 시도해 주세요.",
    emptyStart: "설정된 작업 공간을 분석해 라우트 선언을 수집하세요.",
    emptyScanning: "설정된 작업 공간에서 소스 선언을 수집하고 있습니다.",
    emptyPartial:
      "지원 범위에서 라우트를 찾지 못했습니다. 미해석 선언과 진단 내용을 확인하세요.",
    emptyBounded:
      "지원 범위에서 라우트를 찾지 못했습니다. endpoint의 부재나 접근통제의 안전성을 뜻하지 않습니다.",
    partialNotice:
      "오류 또는 미해석 선언이 있습니다. 부분 결과이므로 전체 endpoint나 접근통제의 안전성을 보장하지 않습니다.",
    legacy: "기존 형식의 파싱 오류",
  },
};

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function text(value: unknown): value is string {
  return typeof value === "string" && value.length <= 16384;
}
function count(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function list(value: unknown): value is unknown[] {
  return Array.isArray(value) && value.length <= 10000;
}
function validReport(value: unknown): value is Report {
  if (
    !object(value) ||
    !text(value.root) ||
    !count(value.python_files) ||
    !count(value.route_count) ||
    !text(value.codex_status) ||
    !list(value.routes) ||
    value.route_count !== value.routes.length ||
    !list(value.parse_errors) ||
    !value.parse_errors.every(text)
  )
    return false;
  if (value.schema_version !== undefined && !text(value.schema_version))
    return false;
  if (
    value.analysis_status !== undefined &&
    value.analysis_status !== "bounded" &&
    value.analysis_status !== "partial"
  )
    return false;
  if (
    !value.routes.every(
      (route) =>
        object(route) &&
        text(route.path) &&
        text(route.function) &&
        text(route.file) &&
        count(route.line) &&
        route.line > 0 &&
        list(route.methods) &&
        route.methods.length > 0 &&
        route.methods.every(text) &&
        (route.registration_id === undefined ||
          route.registration_id === null ||
          text(route.registration_id)),
    )
  )
    return false;
  return (
    value.diagnostics === undefined ||
    (list(value.diagnostics) &&
      value.diagnostics.every(
        (diagnostic) =>
          object(diagnostic) &&
          text(diagnostic.code) &&
          text(diagnostic.message) &&
          (diagnostic.severity === "warning" ||
            diagnostic.severity === "error") &&
          object(diagnostic.location) &&
          text(diagnostic.location.file) &&
          (diagnostic.location.line === null ||
            (count(diagnostic.location.line) &&
              diagnostic.location.line > 0)) &&
          (diagnostic.location.column === null ||
            count(diagnostic.location.column)),
      ))
  );
}

export default function ScanPanel({ language, health }: Props) {
  const t = copy[language];
  const [report, setReport] = useState<Report | null>(null);
  const [failed, setFailed] = useState(false);
  const [scanning, setScanning] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function submitScan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setFailed(false);
    setReport(null);
    setScanning(true);
    try {
      const response = await fetch("/api/scans", {
        method: "POST",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("scan-request-failed");
      const value: unknown = await response.json();
      if (!validReport(value)) throw new Error("invalid-scan-report");
      if (!controller.signal.aborted) setReport(value);
    } catch {
      if (!controller.signal.aborted) setFailed(true);
    } finally {
      if (!controller.signal.aborted) setScanning(false);
    }
  }

  const partial =
    report?.analysis_status === "partial" ||
    (report?.parse_errors.length ?? 0) > 0 ||
    (report?.diagnostics?.length ?? 0) > 0;
  const status = scanning
    ? t.scanning
    : failed
      ? t.failed
      : !report
        ? t.notScanned
        : partial
          ? t.partial
          : t.bounded;
  const empty = scanning
    ? t.emptyScanning
    : failed
      ? t.requestError
      : !report
        ? t.emptyStart
        : partial
          ? t.emptyPartial
          : t.emptyBounded;

  return (
    <>
      <section className="hero" aria-labelledby="scan-title">
        <p className="eyebrow">{t.eyebrow}</p>
        <h1 id="scan-title">{t.title}</h1>
        <p className="hero-copy">{t.intro}</p>
        <form className="scan-form" onSubmit={submitScan} aria-busy={scanning}>
          <label htmlFor="scan-workspace">{t.workspace}</label>
          <div className="scan-controls">
            <output id="scan-workspace" className="workspace-value">
              {report?.root ?? t.configured}
            </output>
            <button type="submit" disabled={scanning || health !== "online"}>
              {scanning ? t.scanning : t.analyze}
            </button>
          </div>
          {failed && (
            <p className="error" role="alert">
              {t.requestError}
            </p>
          )}
        </form>
      </section>
      <section
        className="dashboard"
        aria-label={t.summary}
        aria-busy={scanning}
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">{t.overview}</p>
            <h2>{report?.root ?? t.workspace}</h2>
          </div>
          <span className="adapter">
            {t.codex} · {report?.codex_status ?? t.disabled}
          </span>
        </div>
        <div className="metrics">
          <article>
            <span>{t.files}</span>
            <strong>{report?.python_files ?? "—"}</strong>
          </article>
          <article>
            <span>{t.routes}</span>
            <strong>{report?.route_count ?? "—"}</strong>
          </article>
          <article>
            <span>{t.diagnostics}</span>
            <strong>
              {report
                ? report.diagnostics?.length || report.parse_errors.length
                : "—"}
            </strong>
          </article>
        </div>
        <div className="route-panel">
          <div className="route-title">
            <h3>{t.discovered}</h3>
            <span role="status">
              {report ? `${report.route_count} ${t.total} · ${status}` : status}
            </span>
          </div>
          {report && partial && (
            <div className="parse-errors" role="status">
              <p>{t.partialNotice}</p>
              <ul>
                {report.diagnostics?.map((diagnostic, index) => (
                  <li key={`${index}:${diagnostic.code}`}>
                    [{diagnostic.severity}:{diagnostic.code}]{" "}
                    {diagnostic.location.file}:{diagnostic.location.line ?? "?"}
                    :{diagnostic.location.column ?? "?"} {diagnostic.message}
                  </li>
                ))}
              </ul>
              {report.parse_errors.length > 0 && (
                <details>
                  <summary>
                    {t.legacy} ({report.parse_errors.length})
                  </summary>
                  <ul>
                    {report.parse_errors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
          {!report || report.routes.length === 0 ? (
            <div className="empty-state">
              <span aria-hidden="true">⌁</span>
              <p>{empty}</p>
            </div>
          ) : (
            <ul className="route-list">
              {report.routes.map((route, index) => (
                <li key={`${route.registration_id ?? route.file}:${index}`}>
                  <code className="method">{route.methods.join(",")}</code>
                  <code>{route.path}</code>
                  <span>
                    {route.file}:{route.line}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </>
  );
}
