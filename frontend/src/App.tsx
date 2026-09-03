import { FormEvent, useEffect, useState } from "react";

type HealthState = "checking" | "online" | "offline";

type RouteResult = {
  path: string;
  methods: string[];
  function: string;
  file: string;
  line: number;
};

type ScanReport = {
  root: string;
  python_files: number;
  route_count: number;
  routes: RouteResult[];
  parse_errors: string[];
  codex_status: string;
};

const emptyReport: ScanReport = {
  root: "분석할 저장소를 선택하세요",
  python_files: 0,
  route_count: 0,
  routes: [],
  parse_errors: [],
  codex_status: "disabled",
};

function App() {
  const [health, setHealth] = useState<HealthState>("checking");
  const [path, setPath] = useState("");
  const [report, setReport] = useState<ScanReport>(emptyReport);
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
    setScanning(true);
    try {
      const response = await fetch("/api/scans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
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

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="AuthZest home">
          <span className="brand-mark">AG</span>
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
        <p className="eyebrow">SOURCE-AWARE SECURITY</p>
        <h1>
          접근통제의 빈틈을
          <br />
          코드에서 먼저 찾습니다.
        </h1>
        <p className="hero-copy">
          FastAPI 라우트와 권한 흐름을 분석하기 위한 로컬 우선 보안 테스트
          워크벤치입니다.
        </p>

        <form className="scan-form" onSubmit={submitScan}>
          <label htmlFor="repository">Repository path</label>
          <div className="scan-controls">
            <input
              id="repository"
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="/Users/me/projects/my-fastapi-app"
              required
            />
            <button type="submit" disabled={scanning || health !== "online"}>
              {scanning ? "분석 중…" : "Analyze repository"}
            </button>
          </div>
          {error && <p className="error">{error}</p>}
        </form>
      </section>

      <section className="dashboard" aria-label="Analysis summary">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ANALYSIS OVERVIEW</p>
            <h2>{report.root}</h2>
          </div>
          <span className="adapter">Codex adapter · {report.codex_status}</span>
        </div>

        <div className="metrics">
          <article>
            <span>Python files</span>
            <strong>{report.python_files}</strong>
          </article>
          <article>
            <span>API routes</span>
            <strong>{report.route_count}</strong>
          </article>
          <article>
            <span>Parse errors</span>
            <strong>{report.parse_errors.length}</strong>
          </article>
        </div>

        <div className="route-panel">
          <div className="route-title">
            <h3>Discovered routes</h3>
            <span>{report.route_count} total</span>
          </div>
          {report.routes.length === 0 ? (
            <div className="empty-state">
              <span>⌁</span>
              <p>
                저장소를 분석하면 발견한 FastAPI 라우트가 여기에 표시됩니다.
              </p>
            </div>
          ) : (
            <ul className="route-list">
              {report.routes.map((route) => (
                <li key={`${route.file}:${route.line}:${route.path}`}>
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
