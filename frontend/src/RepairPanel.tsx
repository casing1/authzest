import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { Health, Language } from "./viewer-types.js";
import WorkflowResult from "./WorkflowResult.js";
import { visibleText } from "./viewer-text.js";
import {
  RepairAPIError,
  cancelRepair,
  decideRepair,
  downloadRepairResult,
  getRepairSession,
  inspectRepairAccount,
  startRepair,
} from "./repair-client.js";
import { activeRepair, repairStages } from "./repair-types.js";
import type {
  RepairDiagnostics,
  RepairPending,
  RepairRun,
} from "./repair-types.js";
import { repairMessages } from "./repair-text.js";
import type { RepairErrorText } from "./repair-text.js";

type Props = { language: Language; health: Health; token: string | null };
type Command = (signal: AbortSignal, epoch: number) => Promise<void>;

function errorText(error: unknown): RepairErrorText {
  if (!(error instanceof RepairAPIError) || error.status === 0)
    return "connectedError";
  if ([401, 403, 404].includes(error.status)) return "authError";
  if ([409, 410].includes(error.status)) return "conflictError";
  if (error.status === 422) return "inputError";
  return "actionError";
}
function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
function phrase(pending: RepairPending): string {
  return /^Type '([^'\n]{1,512})'/.exec(pending.prompt)?.[1] ?? "";
}

function CodeBlock({ title, text }: { title: string; text: string }) {
  return (
    <details className="code-details" open>
      <summary>{visibleText(title)}</summary>
      <pre tabIndex={0}>
        <code>{visibleText(text)}</code>
      </pre>
    </details>
  );
}

export function RepairPlan({
  pending,
  language,
}: {
  pending: RepairPending;
  language: Language;
}) {
  const t = repairMessages[language];
  const inputs = record(pending.plan.inputs);
  const request = record(inputs?.request) ?? record(pending.plan.request);
  const source = record(request?.source);
  const proposal = record(inputs?.proposal);
  const runtime = record(pending.plan.runtime);
  const profile = record(runtime?.profile);
  const scope = record(pending.plan.scope);
  const diffs = Array.isArray(inputs?.diffs) ? inputs.diffs : [];
  const policy = Array.isArray(request?.policy)
    ? request.policy.filter((item): item is string => typeof item === "string")
    : [];
  return (
    <>
      {profile ? (
        <section className="repair-runtime">
          <h3>{t.runtimeDetails}</h3>
          <dl className="facts">
            <div>
              <dt>{t.image}</dt>
              <dd>
                {typeof profile.image_id === "string"
                  ? visibleText(profile.image_id)
                  : t.unknown}
              </dd>
            </div>
            <div>
              <dt>{t.platform}</dt>
              <dd>
                {typeof profile.platform === "string"
                  ? visibleText(profile.platform)
                  : t.unknown}
              </dd>
            </div>
            {scope && typeof scope.network === "string" ? (
              <div>
                <dt>{t.network}</dt>
                <dd>{visibleText(scope.network)}</dd>
              </div>
            ) : null}
            {scope &&
            typeof scope.phase_seconds === "number" &&
            typeof scope.cleanup_seconds === "number" ? (
              <div>
                <dt>{t.phaseBudget}</dt>
                <dd>
                  {scope.phase_seconds} / {scope.cleanup_seconds}
                </dd>
              </div>
            ) : null}
          </dl>
        </section>
      ) : null}
      {policy.length ? (
        <div className="text-list">
          <h3>{t.policy}</h3>
          <ul>
            {policy.map((item, i) => (
              <li key={i}>{visibleText(item)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {source && typeof source.text === "string" ? (
        <CodeBlock
          title={`${t.source} · ${typeof source.path === "string" ? source.path : "availability.py"}`}
          text={source.text}
        />
      ) : null}
      {proposal && typeof proposal.rationale === "string" ? (
        <div>
          <h3>{t.rationale}</h3>
          <p className="model-text">{visibleText(proposal.rationale)}</p>
        </div>
      ) : null}
      {proposal && typeof proposal.source === "string" ? (
        <CodeBlock title={t.proposed} text={proposal.source} />
      ) : null}
      {proposal && typeof proposal.test === "string" ? (
        <CodeBlock title={t.test} text={proposal.test} />
      ) : null}
      {diffs.map((item, i) => {
        const change = record(item);
        return change && typeof change.diff === "string" ? (
          <CodeBlock
            key={i}
            title={`${t.diffs} · ${typeof change.path === "string" ? change.path : ""}`}
            text={change.diff}
          />
        ) : null;
      })}
      <details className="code-details full-current-plan">
        <summary>{t.fullPlan}</summary>
        <pre tabIndex={0}>
          <code>{visibleText(JSON.stringify(pending.plan, null, 2))}</code>
        </pre>
      </details>
    </>
  );
}

export function RepairStatus({
  run,
  language,
}: {
  run: RepairRun;
  language: Language;
}) {
  const t = repairMessages[language];
  const stage = run.pending?.stage ?? run.events.at(-1)?.stage;
  const stageLabel = repairStages.includes(
    stage as (typeof repairStages)[number],
  )
    ? t[stage as (typeof repairStages)[number]]
    : stage;
  return (
    <section className="result-panel repair-progress" aria-live="polite">
      <h2>{t[run.state]}</h2>
      {stageLabel ? (
        <p>
          {t.stage} · <strong>{visibleText(stageLabel)}</strong>
        </p>
      ) : null}
      {run.failure ? <p className="error">{visibleText(run.failure)}</p> : null}
      {run.view?.summary.recovery_required ? (
        <aside className="recorded-error">
          <h3>{t.recovery}</h3>
          <p>{t.recoveryNote}</p>
        </aside>
      ) : null}
      <details className="repair-activity" open>
        <summary>{t.activity}</summary>
        <p className="muted">{t.activityNote}</p>
        <ol>
          {run.events.map((event) => (
            <li key={event.sequence}>
              <span>
                {repairStages.includes(
                  event.stage as (typeof repairStages)[number],
                )
                  ? t[event.stage as (typeof repairStages)[number]]
                  : visibleText(event.stage)}
              </span>
              <code>{visibleText(event.status)}</code>
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}

export default function RepairPanel({ language, health, token }: Props) {
  const t = repairMessages[language];
  const [model, setModel] = useState("gpt-6-astra");
  const [run, setRun] = useState<RepairRun | null>(null);
  const [diagnostics, setDiagnostics] = useState<RepairDiagnostics | null>(
    null,
  );
  const [loaded, setLoaded] = useState(false);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<RepairErrorText | null>(null);
  const [answer, setAnswer] = useState({ promptID: "", text: "" });
  const alive = useRef(false);
  const commandEpoch = useRef(0);
  const commandBusy = useRef(false);
  const commandAbort = useRef<AbortController | null>(null);
  const shouldPoll =
    error !== "authError" && (run === null || activeRepair(run) || !connected);
  const accept = useCallback((value: RepairRun | null, epoch: number) => {
    if (!alive.current || epoch !== commandEpoch.current) return;
    setRun((previous) =>
      previous &&
      value &&
      previous.run_id === value.run_id &&
      previous.revision > value.revision
        ? previous
        : value,
    );
    setConnected(true);
    setLoaded(true);
  }, []);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      commandAbort.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (!token || health !== "online" || !shouldPoll) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    async function poll() {
      if (commandBusy.current) {
        if (!stopped)
          timer = setTimeout(() => {
            void poll();
          }, 1000);
        return;
      }
      const epoch = commandEpoch.current;
      let retry = true;
      try {
        const current = await getRepairSession(token!, controller.signal);
        if (!stopped) accept(current, epoch);
      } catch (caught) {
        if (stopped || epoch !== commandEpoch.current) return;
        const key = errorText(caught);
        setError(key);
        setConnected(false);
        setLoaded(true);
        retry = key !== "authError";
      } finally {
        if (!stopped && retry)
          timer = setTimeout(() => {
            void poll();
          }, 1000);
      }
    }
    void poll();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [token, health, accept, shouldPoll]);

  async function perform(command: Command, resyncOnFailure = false) {
    if (commandBusy.current || !token || health !== "online" || !connected)
      return;
    commandBusy.current = true;
    const epoch = ++commandEpoch.current;
    const controller = new AbortController();
    commandAbort.current = controller;
    setBusy(true);
    setError(null);
    try {
      await command(controller.signal, epoch);
    } catch (caught) {
      if (
        alive.current &&
        !controller.signal.aborted &&
        epoch === commandEpoch.current
      ) {
        const key = errorText(caught);
        setError(key);
        if (key === "connectedError" || key === "authError")
          setConnected(false);
        if (resyncOnFailure && key !== "authError") {
          // A lost start response may still leave a new run on the server.
          // Read its state once; never retry the start request.
          try {
            accept(await getRepairSession(token, controller.signal), epoch);
          } catch (resyncError) {
            if (
              alive.current &&
              !controller.signal.aborted &&
              epoch === commandEpoch.current
            ) {
              setConnected(false);
              if (errorText(resyncError) === "authError") setError("authError");
            }
          }
        }
      }
    } finally {
      commandBusy.current = false;
      if (alive.current && epoch === commandEpoch.current) setBusy(false);
    }
  }
  function begin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || activeRepair(run)) return;
    void perform(
      async (signal, epoch) =>
        accept(await startRepair(token, model.trim(), signal), epoch),
      true,
    );
  }
  function decide(value: string) {
    const pending = run?.pending;
    if (!token || !run || !pending) return;
    void perform(async (signal, epoch) =>
      accept(
        await decideRepair(token, run.run_id, pending.prompt_id, value, signal),
        epoch,
      ),
    );
  }
  function inspectAccount() {
    if (!token) return;
    void perform(async (signal, epoch) => {
      const status = await inspectRepairAccount(token, signal);
      if (alive.current && epoch === commandEpoch.current)
        setDiagnostics(status);
    });
  }
  function stop() {
    if (!token || !run) return;
    void perform(async (signal, epoch) =>
      accept(await cancelRepair(token, run.run_id, signal), epoch),
    );
  }
  function download() {
    if (!token || !run) return;
    void perform(async (signal, epoch) => {
      const blob = await downloadRepairResult(token, run.run_id, signal);
      if (!alive.current || epoch !== commandEpoch.current) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `authzest-owner-read-${run.run_id}.json`;
      try {
        document.body.append(link);
        link.click();
      } finally {
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    });
  }
  const active = activeRepair(run);
  const enabled =
    token !== null && health === "online" && loaded && connected && !busy;
  const pending = run?.pending;
  const currentAnswer =
    pending && answer.promptID === pending.prompt_id ? answer.text : "";
  const expected = pending ? phrase(pending) : "";
  return (
    <>
      <section className="hero">
        <p className="eyebrow">{t.eyebrow}</p>
        <h1>{t.title}</h1>
        <p className="hero-copy">{t.intro}</p>
      </section>
      <aside className="read-only repair-scope">
        <span className="tag">{t.scope}</span>
        <p>{t.scopeNote}</p>
      </aside>
      {!token ? (
        <section className="result-panel">
          <h2>{t.locked}</h2>
          <p>{t.launch}</p>
          <pre>
            <code>
              authzest ui --ai-runtime-config /absolute/private/runtime.json
            </code>
          </pre>
          <p className="muted">{t.launchNote}</p>
        </section>
      ) : null}
      <section className="result-panel repair-connection">
        <h2>{t.account}</h2>
        <dl className="facts">
          <div>
            <dt>{t.account}</dt>
            <dd>{diagnostics ? t[diagnostics.codex_status] : t.unchecked}</dd>
          </div>
          <div>
            <dt>{t.version}</dt>
            <dd>{diagnostics ? t[diagnostics.version_status] : t.unchecked}</dd>
          </div>
        </dl>
        <p className="muted">{t.accountNote}</p>
        <button
          type="button"
          className="secondary"
          disabled={!enabled || active}
          onClick={inspectAccount}
        >
          {t.accountCheck}
        </button>
        <form className="repair-start" onSubmit={begin} aria-busy={busy}>
          <label htmlFor="repair-model">{t.model}</label>
          <input
            id="repair-model"
            value={model}
            maxLength={128}
            required
            autoComplete="off"
            spellCheck={false}
            disabled={!token || active || busy}
            onChange={(event) => setModel(event.target.value)}
          />
          <button
            type="submit"
            className="primary"
            disabled={!enabled || active || !model.trim()}
          >
            {busy ? t.busy : t.start}
          </button>
          <p className="muted">{t.startNote}</p>
        </form>
        {token && !loaded ? <p role="status">{t.checking}</p> : null}
        {error ? (
          <p role="alert" className="error">
            {t[error]}
          </p>
        ) : null}
      </section>
      {run ? (
        <RepairStatus run={run} language={language} />
      ) : (
        <section className="empty-state result-empty">
          <p>{t.noActivity}</p>
        </section>
      )}
      {pending ? (
        <section className="result-panel repair-decision" aria-busy={busy}>
          <h2>
            {t.review} · {t[pending.stage]}
          </h2>
          <p>{t.reviewNote}</p>
          <RepairPlan pending={pending} language={language} />
          <p className="repair-deadline" role="status">
            {Math.ceil(pending.remaining_seconds)} {t.remaining}
          </p>
          {pending.remaining_seconds <= 0 ? (
            <p className="error">{t.expired}</p>
          ) : null}
          <h3>{t.confirmation}</h3>
          <pre className="repair-phrase">
            <code>{visibleText(expected || pending.prompt)}</code>
          </pre>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              decide(currentAnswer);
            }}
          >
            <label htmlFor="repair-answer">{t.answer}</label>
            <textarea
              id="repair-answer"
              rows={3}
              autoComplete="off"
              spellCheck={false}
              maxLength={512}
              value={currentAnswer}
              disabled={!enabled || pending.remaining_seconds <= 0}
              onChange={(event) =>
                setAnswer({
                  promptID: pending.prompt_id,
                  text: event.target.value,
                })
              }
            />
            <div className="form-actions">
              <button
                className="primary"
                type="submit"
                disabled={
                  !enabled ||
                  !expected ||
                  currentAnswer !== expected ||
                  pending.remaining_seconds <= 0
                }
              >
                {t.approve}
              </button>
              <button
                className="secondary"
                type="button"
                disabled={!enabled}
                onClick={() => decide("")}
              >
                {t.decline}
              </button>
            </div>
          </form>
        </section>
      ) : null}
      {active ? (
        <section className="result-panel">
          <button
            className="secondary"
            type="button"
            disabled={!enabled || run?.cancel_requested}
            onClick={stop}
          >
            {t.stop}
          </button>
          <p className="muted">{t.stopNote}</p>
        </section>
      ) : null}
      {run?.result_available ? (
        <section className="result-panel">
          <button
            className="primary"
            type="button"
            disabled={!enabled}
            onClick={download}
          >
            {t.download}
          </button>
          <p className="muted">{t.resultNote}</p>
          {run.view_error ? <p className="error">{t.viewUnavailable}</p> : null}
        </section>
      ) : null}
      {run?.view ? (
        <WorkflowResult view={run.view} language={language} />
      ) : null}
    </>
  );
}
