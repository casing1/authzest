import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { Health, Language, WorkflowView } from "./viewer-types.js";
import { textFor, visibleText } from "./viewer-text.js";
import WorkflowResult from "./WorkflowResult.js";

const MAX_BYTES = 512 * 1024;

export default function ResultViewer({
  language,
  health,
}: {
  language: Language;
  health: Health;
}) {
  const t = textFor(language);
  const [view, setView] = useState<WorkflowView | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<
    "failed" | "tooLarge" | "unsupported" | null
  >(null);
  const [loading, setLoading] = useState(false);
  const active = useRef<AbortController | null>(null);
  const chooser = useRef<HTMLInputElement | null>(null);
  useEffect(() => () => active.current?.abort(), []);

  function clear() {
    active.current?.abort();
    active.current = null;
    setView(null);
    setFile(null);
    setError(null);
    setLoading(false);
    if (chooser.current) chooser.current.value = "";
  }

  async function openResult(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setView(null);
    setError(null);
    if (file.size > MAX_BYTES) {
      setError("tooLarge");
      return;
    }
    setLoading(true);
    try {
      const content = await file.arrayBuffer();
      if (controller.signal.aborted) return;
      const response = await fetch("/api/results/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: content,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (!response.ok) {
        setError(
          response.status === 413
            ? "tooLarge"
            : response.status === 422
              ? "unsupported"
              : "failed",
        );
        return;
      }
      const data = (await response.json()) as WorkflowView;
      if (
        data.kind !== "authzest-workflow-view" ||
        data.schema_version !== "1.0" ||
        data.provenance !== "imported-unverified"
      )
        throw new Error("Unexpected response");
      if (!controller.signal.aborted) setView(data);
    } catch {
      if (!controller.signal.aborted) setError("failed");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  return (
    <>
      <aside className="read-only">
        <span className="tag">{t.readOnly}</span>
        <p>{t.readOnlyNote}</p>
      </aside>
      <details className="import-panel" open={!view}>
        <summary className="import-summary">
          {t.importTitle}
          {view && file ? ` · ${visibleText(file.name)}` : ""}
        </summary>
        <div>
          <p className="muted">{t.importCopy}</p>
        </div>
        <form onSubmit={openResult} aria-busy={loading}>
          <label htmlFor="result-json">{t.choose}</label>
          <input
            id="result-json"
            type="file"
            accept=".json,application/json"
            ref={chooser}
            onChange={(event) => {
              active.current?.abort();
              setView(null);
              setLoading(false);
              setError(null);
              setFile(event.target.files?.[0] ?? null);
            }}
          />
          <div className="form-actions">
            <button
              className="primary"
              type="submit"
              disabled={!file || loading || health !== "online"}
            >
              {loading ? t.importing : t.import}
            </button>
            <button
              className="secondary"
              type="button"
              onClick={clear}
              disabled={!file && !view && !error}
            >
              {t.clear}
            </button>
          </div>
        </form>
        {error ? (
          <p className="error" role="alert">
            {t[error]}
          </p>
        ) : null}
        <p className="import-status" role="status">
          {loading
            ? t.importing
            : view && file
              ? `${t.selected}: ${visibleText(file.name)}`
              : ""}
        </p>
      </details>
      {view ? (
        <WorkflowResult view={view} language={language} />
      ) : !loading && !error ? (
        <section className="empty-state result-empty">
          <span aria-hidden="true">⌁</span>
          <h2>{t.none}</h2>
          <p>{t.noneCopy}</p>
        </section>
      ) : null}
    </>
  );
}
