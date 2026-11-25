import type { ReactNode } from "react";
import type { Failure, Language, Phase, WorkflowView } from "./viewer-types.js";
import { textFor, visibleText } from "./viewer-text.js";

type Props = { view: WorkflowView; language: Language };

function valueText(value: unknown, language: Language): string {
  const t = textFor(language);
  if (value === null || value === undefined) return t.unknown;
  if (value === true) return t.yes;
  if (value === false) return t.no;
  return visibleText(String(value));
}

function Facts({
  items,
  language,
}: {
  items: [string, unknown][];
  language: Language;
}) {
  return (
    <dl className="facts">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{valueText(value, language)}</dd>
        </div>
      ))}
    </dl>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="result-panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <details className="code-details" open>
      <summary>{visibleText(title)}</summary>
      <pre tabIndex={0}>
        <code>{visibleText(text)}</code>
      </pre>
    </details>
  );
}

function TextList({
  title,
  items,
  language,
}: {
  title: string;
  items: string[];
  language: Language;
}) {
  return (
    <div className="text-list">
      <h3>{title}</h3>
      {items.length ? (
        <ul>
          {items.map((item, i) => (
            <li key={i}>{visibleText(item)}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{textFor(language).noItems}</p>
      )}
    </div>
  );
}

function FailureNotice({
  failure,
  title,
  language,
}: {
  failure: Failure | null;
  title: string;
  language: Language;
}) {
  if (!failure) return null;
  const t = textFor(language);
  return (
    <aside className="recorded-error">
      <h3>{title}</h3>
      <Facts
        language={language}
        items={[
          [t.stage, failure.stage],
          [t.reason, failure.code],
          ["turn_start", failure.turn_start],
        ]}
      />
    </aside>
  );
}

function HttpPhaseCard({
  phase,
  title,
  language,
}: {
  phase: Phase | null;
  title: string;
  language: Language;
}) {
  const t = textFor(language);
  const comparison = phase?.comparison;
  return (
    <article className="phase-card">
      <h3>{title}</h3>
      {!phase ? (
        <p className="muted">{t.noPhase}</p>
      ) : (
        <>
          <Facts
            language={language}
            items={[
              [t.phaseStatus, phase.status],
              [t.httpRegression, phase.regression_status],
              [t.cleanup, phase.cleanup_confirmed],
              [t.comparison, comparison?.comparison_status],
              [t.matches, comparison?.matches_expected_profile],
              [
                t.cases,
                comparison
                  ? `${comparison.matching_case_count} / ${comparison.case_count}`
                  : null,
              ],
            ]}
          />
          {phase.case_outcomes && phase.case_outcomes.length > 0 ? (
            <>
              <h4>{t.caseOutcomes}</h4>
              <ul className="case-outcomes">
                {phase.case_outcomes.map((row) => (
                  <li key={row.case_id}>
                    <code>{visibleText(row.case_id)}</code>{" "}
                    {visibleText(row.outcome)}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <details className="hash-details">
            <summary>SHA-256</summary>
            <Facts
              language={language}
              items={[
                [t.sourceHash, phase.application_sha256],
                [t.scheduleHash, phase.test_sha256],
              ]}
            />
          </details>
          <FailureNotice
            failure={phase.failure}
            title={t.errorTitle}
            language={language}
          />
        </>
      )}
    </article>
  );
}

function PhaseCard({
  phase,
  title,
  language,
  ownerRead,
  httpFix = false,
}: {
  phase: Phase | null;
  title: string;
  language: Language;
  ownerRead: boolean;
  httpFix?: boolean;
}) {
  if (httpFix)
    return <HttpPhaseCard phase={phase} title={title} language={language} />;
  const t = textFor(language);
  const comparison = phase?.comparison;
  const facts: [string, unknown][] = [[t.phaseStatus, phase?.status]];
  if (ownerRead) {
    facts.push(
      [t.httpStatus, phase?.response_status],
      [t.regression, phase?.regression_status],
    );
  }
  facts.push(
    [t.testExit, phase?.test_exit_code],
    [t.attempted, phase?.generated_runtime_attempted],
    [t.cleanup, phase?.cleanup_confirmed],
    [t.profile, comparison?.expected_profile],
    [t.comparison, comparison?.comparison_status],
    [t.matches, comparison?.matches_expected_profile],
    [
      ownerRead ? t.profileCases : t.cases,
      comparison
        ? `${comparison.matching_case_count} / ${comparison.case_count}`
        : null,
    ],
  );
  if (ownerRead) {
    facts.push([
      t.intendedCases,
      comparison?.intended_match_count !== null &&
      comparison?.intended_match_count !== undefined
        ? `${comparison.intended_match_count} / ${comparison.case_count}`
        : null,
    ]);
  } else {
    facts.push([
      t.requests,
      comparison
        ? `${comparison.matching_request_count} / ${comparison.request_count}`
        : null,
    ]);
  }
  return (
    <article className="phase-card">
      <h3>{title}</h3>
      {!phase ? (
        <p className="muted">{t.noPhase}</p>
      ) : (
        <>
          <Facts language={language} items={facts} />
          <details className="hash-details">
            <summary>SHA-256</summary>
            <Facts
              language={language}
              items={[
                [
                  ownerRead ? t.ruleHash : t.sourceHash,
                  phase.application_sha256,
                ],
                [t.testHash, phase.test_sha256],
              ]}
            />
          </details>
          <FailureNotice
            failure={phase.failure}
            title={t.errorTitle}
            language={language}
          />
          <FailureNotice
            failure={phase.transport_failure}
            title={t.transportError}
            language={language}
          />
        </>
      )}
    </article>
  );
}

function declarationTitle(declaration: unknown, index: number): string {
  if (!declaration || typeof declaration !== "object") return `#${index + 1}`;
  const value = declaration as Record<string, unknown>;
  const methods = Array.isArray(value.methods)
    ? value.methods.filter((x) => typeof x === "string").join(", ")
    : "";
  return `${methods} ${typeof value.path === "string" ? value.path : `#${index + 1}`}`;
}

export default function WorkflowResult({ view, language }: Props) {
  const t = textFor(language),
    summary = view.summary,
    session = view.session,
    source = view.source_evidence,
    proposal = view.proposal;
  const ownerRead = view.record_kind === "owner-read-suggestion";
  const httpFix = view.record_kind === "repository-http-fix-result";
  const summaryFacts: [string, unknown][] = [
    [t.workflow, summary.status],
    [t.proposal, summary.proposal_status],
    [t.exit, summary.exit_code],
    [t.execution, summary.execution_status],
    [t.application, summary.patch_application],
    [t.copyState, summary.current_copy_state],
    [t.restoration, summary.restoration_status],
    [t.original, summary.original_checkout_modified],
  ];
  if (ownerRead || summary.recovery_required !== undefined) {
    summaryFacts.push([t.recoveryRequired, summary.recovery_required]);
  }
  if (httpFix) {
    summaryFacts.push([t.reviewedCasesMatched, session?.verified_fix]);
  }
  return (
    <div className="workflow-result">
      <aside className="import-notice">
        <strong>{t.imported}</strong>
        <p>{t.importedNote}</p>
      </aside>
      {view.record_version === "legacy-unversioned" ? (
        <aside className="import-notice legacy">
          <strong>{t.legacy}</strong>
          <p>{t.legacyNote}</p>
        </aside>
      ) : null}
      <Panel title={t.summary}>
        <Facts language={language} items={summaryFacts} />
        <FailureNotice
          failure={view.failure}
          title={t.errorTitle}
          language={language}
        />
      </Panel>
      <Panel title={t.checks}>
        <p className="muted">{t.checksNote}</p>
        <div className="phase-grid">
          <PhaseCard
            title={t.before}
            phase={session?.checks.before ?? null}
            language={language}
            ownerRead={ownerRead}
            httpFix={httpFix}
          />
          <PhaseCard
            title={t.after}
            phase={session?.checks.after ?? null}
            language={language}
            ownerRead={ownerRead}
            httpFix={httpFix}
          />
        </div>
        <p className="footnote">{t.captures}</p>
      </Panel>
      <Panel title={t.source}>
        {source ? (
          <>
            <Facts
              language={language}
              items={[
                [t.scenario, source.scenario_id],
                [t.policyAuthor, source.policy_authorship],
                [t.policyReview, source.policy_review],
              ]}
            />
            <TextList
              title={t.policy}
              items={source.policy}
              language={language}
            />
            <TextBlock
              title={`${t.beforeSource} · ${source.source.path}`}
              text={source.source.text}
            />
            <details className="hash-details">
              <summary>SHA-256</summary>
              <code>{source.source.sha256}</code>
            </details>
            {!ownerRead || source.declarations.length > 0 ? (
              <>
                <h3>{t.declarations}</h3>
                {source.declarations.map((item, index) => (
                  <details className="declaration" key={index}>
                    <summary>
                      {visibleText(declarationTitle(item, index))}
                    </summary>
                    <pre tabIndex={0}>
                      {visibleText(JSON.stringify(item, null, 2))}
                    </pre>
                  </details>
                ))}
              </>
            ) : null}
          </>
        ) : (
          <p className="muted">{t.noSource}</p>
        )}
      </Panel>
      <Panel title={t.generated}>
        {proposal ? (
          <>
            <h3>{t.rationale}</h3>
            <p className="model-text">{visibleText(proposal.rationale)}</p>
            <div className="explanation-grid">
              <TextList
                title={t.assumptions}
                items={proposal.assumptions}
                language={language}
              />
              <TextList
                title={t.uncertainties}
                items={proposal.uncertainties}
                language={language}
              />
            </div>
            <TextList
              title={t.limitations}
              items={proposal.limitations}
              language={language}
            />
            <TextBlock
              title={`${t.test} · ${proposal.test.path}`}
              text={proposal.test.text}
            />
            <TextBlock
              title={`${t.afterSource} · ${proposal.after_source.path}`}
              text={proposal.after_source.text}
            />
            <h3>{t.proposedDiff}</h3>
            <p className="muted">{t.diffNote}</p>
            {proposal.changes.map((change) => (
              <div className="change" key={change.path}>
                <TextBlock title={change.path} text={change.diff} />
                <details className="hash-details">
                  <summary>SHA-256</summary>
                  <Facts
                    language={language}
                    items={[
                      [t.beforeHash, change.before_sha256 ?? t.absent],
                      [t.afterHash, change.after_sha256],
                    ]}
                  />
                </details>
              </div>
            ))}
          </>
        ) : (
          <>
            <p className="muted">{t.noProposal}</p>
            {view.assessment ? (
              <>
                <h3>{t.rationale}</h3>
                <p className="model-text">
                  {visibleText(view.assessment.rationale)}
                </p>
                <TextList
                  title={t.assumptions}
                  items={view.assessment.assumptions}
                  language={language}
                />
                <TextList
                  title={t.uncertainties}
                  items={view.assessment.uncertainties}
                  language={language}
                />
                <TextList
                  title={t.limitations}
                  items={view.assessment.limitations}
                  language={language}
                />
              </>
            ) : null}
          </>
        )}
      </Panel>
      <Panel title={t.decisions}>
        <p className="muted">{t.decisionsNote}</p>
        {session ? (
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label={t.decisions}
          >
            <table>
              <thead>
                <tr>
                  {[
                    t.stage,
                    t.decision,
                    t.status,
                    t.attempted,
                    t.dispatched,
                    t.expired,
                    t.reason,
                  ].map((title) => (
                    <th scope="col" key={title}>
                      {title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {session.stages.map((stage) => (
                  <tr key={stage.stage}>
                    {[
                      stage.stage,
                      stage.decision,
                      stage.status,
                      stage.attempted,
                      stage.dispatched,
                      stage.expired,
                      stage.reason,
                    ].map((value, index) => (
                      <td key={index}>{valueText(value, language)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">{t.noSession}</p>
        )}
      </Panel>
      <Panel title={t.recovery}>
        {session ? (
          <Facts
            language={language}
            items={[
              [t.sessionClosed, session.closed],
              [t.close, session.close_status],
              [t.inputCleanup, session.runtime_input_cleanup],
              [t.cleanupUnconfirmed, session.cleanup_unconfirmed],
              [t.clockUnconfirmed, session.clock_unconfirmed],
              [t.authorization, session.authorization_status],
              [t.verified, session.verified_fix],
              [t.isolation, session.isolation_established],
              [t.resources, session.resource_enforcement_established],
              [t.authenticity, session.test_report_authenticity],
            ]}
          />
        ) : (
          <p className="muted">{t.noSession}</p>
        )}
      </Panel>
      <aside className="import-notice">
        <strong>{t.notice}</strong>
        <p>{t.displayNote}</p>
      </aside>
    </div>
  );
}
