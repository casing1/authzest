import { FormEvent, useEffect, useState } from "react";

type HealthState = "checking" | "online" | "offline";

type RouteResult = {
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

type ScanReport = {
  root: string;
  python_files: number;
  route_count: number;
  routes: RouteResult[];
  parse_errors: string[];
  codex_status: string;
  schema_version?: string;
  analysis_status?: "bounded" | "partial";
  diagnostics?: Diagnostic[];
};

function App() {
  const [health, setHealth] = useState<HealthState>("checking");
  const [report, setReport] = useState<ScanReport | null>(null);
  const [error, setError] = useState("");
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    fetch("/api/health")
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        setHealth("online");
      })
      .catch(() => setHealth("offline"));
  }, []);

  async function submitScan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setReport(null);
    setScanning(true);
    try {
      const response = await fetch("/api/scans", {
        method: "POST",
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail ?? "분석 요청에 실패했습니다.");
      }
      setReport((await response.json()) as ScanReport);
    } catch (scanError) {
      setError(
        scanError instanceof Error
          ? scanError.message
          : "알 수 없는 오류가 발생했습니다.",
      );
    } finally {
      setScanning(false);
    }
  }

  const hasParseErrors = (report?.parse_errors.length ?? 0) > 0;
  const isPartial =
    report?.analysis_status === "partial" ||
    hasParseErrors ||
    (report?.diagnostics?.length ?? 0) > 0;
  const scanStatus = scanning
    ? "Scanning"
    : error
      ? "Scan failed"
      : report === null
        ? "Not scanned"
        : isPartial
          ? "Partial inventory"
          : "Bounded inventory";
  const emptyMessage = scanning
    ? "선택된 저장소의 소스 선언을 수집하고 있습니다."
    : error
      ? "이번 스캔은 실패했습니다. 이전 결과를 표시하지 않습니다. 다시 실행해 주세요."
      : report === null
        ? "아직 스캔하지 않았습니다. Analyze repository를 눌러 라우트를 수집하세요."
        : isPartial
          ? "오류 또는 미해석 선언이 있으며, 지원 범위에서는 라우트를 찾지 못했습니다. 진단 내용을 확인하세요."
          : "스캔을 마쳤지만 지원 범위에서 라우트를 찾지 못했습니다. endpoint의 부재나 접근통제의 안전성을 뜻하지 않습니다.";

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="AuthZest home">
          <span className="brand-mark">AZ</span>
          <span>AuthZest</span>
        </a>
        <div className={`health health-${health}`}>
          <span className="health-dot" />
          {health === "online"
            ? "Engine online"
            : health === "offline"
              ? "Engine offline"
              : "Checking"}
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">STATIC ROUTE INVENTORY</p>
        <h1>
          FastAPI 라우트를
          <br />
          소스에서 확인합니다.
        </h1>
        <p className="hero-copy">
          대상 코드를 실행하지 않고 지원하는 라우트 선언을 수집합니다. 해석하지
          못한 선언은 빠질 수 있으며, 인증·인가의 안전성은 아직 판정하지
          않습니다.
        </p>

        <form className="scan-form" onSubmit={submitScan}>
          <label>Configured workspace</label>
          <div className="scan-controls">
            <div className="workspace-value">
              {report?.root ?? "authzest ui 시작 시 선택한 저장소"}
            </div>
            <button type="submit" disabled={scanning || health !== "online"}>
              {scanning ? "분석 중…" : "Analyze repository"}
            </button>
          </div>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>

      <section className="dashboard" aria-label="Analysis summary">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ANALYSIS OVERVIEW</p>
            <h2>{report?.root ?? "서버에 설정된 workspace"}</h2>
          </div>
          <span className="adapter">
            Codex analysis · {report?.codex_status ?? "disabled"}
          </span>
        </div>

        <div className="metrics">
          <article>
            <span>Python files</span>
            <strong>{report?.python_files ?? "—"}</strong>
          </article>
          <article>
            <span>API routes</span>
            <strong>{report?.route_count ?? "—"}</strong>
          </article>
          <article>
            <span>Diagnostics</span>
            <strong>
              {report
                ? report.diagnostics?.length || report.parse_errors.length
                : "—"}
            </strong>
          </article>
        </div>

        <div className="route-panel">
          <div className="route-title">
            <h3>Discovered routes</h3>
            <span role="status">
              {report
                ? `${report.route_count} total · ${scanStatus}`
                : scanStatus}
            </span>
          </div>
          {report && isPartial && (
            <div className="parse-errors" role="status">
              <p>
                오류 또는 미해석 선언을 확인했습니다. 표시된 라우트는 부분
                결과이며, 전체 endpoint나 접근통제의 안전성을 보장하지 않습니다.
              </p>
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
                    Legacy parse errors ({report.parse_errors.length})
                  </summary>
                  <ul>
                    {report.parse_errors.map((parseError, index) => (
                      <li key={`${index}:${parseError}`}>{parseError}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
          {report === null || report.routes.length === 0 ? (
            <div className="empty-state">
              <span>⌁</span>
              <p>{emptyMessage}</p>
            </div>
          ) : (
            <ul className="route-list">
              {report.routes.map((route, index) => (
                <li
                  key={
                    route.registration_id ??
                    `${route.file}:${route.line}:${route.path}:${route.methods.join(",")}:${index}`
                  }
                >
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
    </main>
  );
}

export default App;
