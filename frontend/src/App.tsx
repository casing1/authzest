import { useEffect, useState } from "react";
import type { Health, Language } from "./viewer-types.js";
import { textFor } from "./viewer-text.js";
import ResultViewer from "./ResultViewer.js";
import ScanPanel from "./ScanPanel.js";

export default function App() {
  const [health, setHealth] = useState<Health>("checking");
  const [language, setLanguage] = useState<Language>("en");
  const [page, setPage] = useState<"results" | "scan">("results");
  const t = textFor(language);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/health", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        if (!controller.signal.aborted) setHealth("online");
      })
      .catch(() => {
        if (!controller.signal.aborted) setHealth("offline");
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);
  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="AuthZest">
          <span className="brand-mark">AZ</span>
          <span>AuthZest</span>
        </a>
        <div className="header-controls">
          <div className={`health health-${health}`} role="status">
            <span className="health-dot" aria-hidden="true" />
            {t[health]}
          </div>
          <select
            aria-label={t.language}
            value={language}
            onChange={(event) => setLanguage(event.target.value as Language)}
          >
            <option value="en">English</option>
            <option value="ko">한국어</option>
          </select>
        </div>
      </header>
      <nav
        className="view-nav"
        aria-label={language === "en" ? "Workspace views" : "워크스페이스 화면"}
      >
        <button
          type="button"
          aria-pressed={page === "results"}
          onClick={() => setPage("results")}
        >
          {t.results}
        </button>
        <button
          type="button"
          aria-pressed={page === "scan"}
          onClick={() => setPage("scan")}
        >
          {t.scan}
        </button>
      </nav>
      {page === "results" ? (
        <>
          <section className="hero">
            <p className="eyebrow">{t.eyebrow}</p>
            <h1>{t.title}</h1>
            <p className="hero-copy">{t.intro}</p>
          </section>
          <ResultViewer language={language} health={health} />
        </>
      ) : (
        <ScanPanel language={language} health={health} />
      )}
      <footer>AuthZest · {t.readOnly}</footer>
    </main>
  );
}
