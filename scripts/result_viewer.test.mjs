import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL, fileURLToPath } from "node:url";
import test, { after } from "node:test";

const frontend = fileURLToPath(new URL("../frontend/", import.meta.url));
const require = createRequire(path.join(frontend, "package.json"));
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
// Compile only these repository-owned components; imported result text is never
// compiled or evaluated. Temporary modules resolve the locked React installation.
fs.mkdirSync(path.join(frontend, "node_modules/.tmp"), { recursive: true });
const build = fs.mkdtempSync(path.join(frontend, "node_modules/.tmp/viewer-tests-"));
after(() => fs.rmSync(build, { recursive: true, force: true }));
for (const name of ["viewer-types.ts", "viewer-text.ts", "WorkflowResult.tsx", "ResultViewer.tsx", "ScanPanel.tsx", "App.tsx"]) {
  const output = ts.transpileModule(fs.readFileSync(path.join(frontend, "src", name), "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX },
  });
  fs.writeFileSync(path.join(build, name.replace(/\.tsx?$/, ".js")), output.outputText);
}
const load = name => import(pathToFileURL(path.join(build, name)));
const { default: App } = await load("App.js");
const { default: WorkflowResult } = await load("WorkflowResult.js");
const { default: ResultViewer } = await load("ResultViewer.js");
const { messages, visibleText } = await load("viewer-text.js");

function view() {
  return {
    schema_version: "1.0", kind: "authzest-workflow-view", record_version: "1.0", provenance: "imported-unverified",
    summary: { status: "file-workflow-cancelled", exit_code: 130, proposal_status: "unknown", execution_status: "not-run", patch_application: "not-run", applied: false, current_copy_state: null, restoration_status: "not-run", original_checkout_modified: false },
    source_evidence: null, proposal: null, assessment: null, session: null, failure: null,
    availability: { before_source: false, declarations: false, raw_phase_captures: false }, warnings: [],
  };
}
const render = (record, language = "en") => renderToStaticMarkup(React.createElement(WorkflowResult, { view: record, language }));

test("all interface messages have English and Korean counterparts", () => {
  assert.deepEqual(Object.keys(messages.en).sort(), Object.keys(messages.ko).sort());
  for (const language of ["en", "ko"]) for (const value of Object.values(messages[language])) assert.ok(value.trim());
});
test("default app is English, empty and does not invent successful observations", () => {
  const html = renderToStaticMarkup(React.createElement(App));
  assert.match(html, /No result loaded/);
  assert.match(html, /Read-only viewer/);
  assert.doesNotMatch(html, /17 \/ 17|21 \/ 21|file-workflow-complete/);
});
test("offline import is disabled and Korean labels are usable", () => {
  const html = renderToStaticMarkup(React.createElement(ResultViewer, { health: "offline", language: "ko" }));
  assert.match(html, /결과 열기/);
  assert.match(html, /type="submit" disabled=""/);
  assert.match(html, /type="file"/);
});
test("missing receipts stay unavailable, without zero-valued results", () => {
  const html = render(view());
  assert.match(html, /No phase receipt/);
  assert.match(html, /Original source and declarations are unavailable/);
  assert.doesNotMatch(html, /0 \/ 0|21 \/ 21/);
});
test("legacy records explicitly disclose absent version and source", () => {
  const record = view(); record.record_version = "legacy-unversioned";
  assert.match(render(record), /Legacy record · unversioned input/);
  assert.match(render(record, "ko"), /과거 기록 · 입력 버전 없음/);
});
test("application history is shown alongside restored current copy state", () => {
  const record = view();
  record.summary.patch_application = "applied-copy-only";
  record.summary.applied = true;
  record.summary.current_copy_state = "restored-before";
  record.summary.restoration_status = "restored-before";
  const html = render(record);
  assert.match(html, /Application history/);
  assert.match(html, /applied-copy-only/);
  assert.match(html, /Current copy state in record/);
  assert.match(html, /restored-before/);
  assert.match(html, /authenticity not established/);
});
test("abstention rationale and uncertainties remain readable with no proposed code", () => {
  const record = view();
  record.assessment = { status: "unknown", rationale: "Insufficient policy evidence.", assumptions: [], uncertainties: ["Owner policy is not confirmed."], limitations: ["No runtime proof."] };
  const html = render(record);
  assert.match(html, /Insufficient policy evidence/);
  assert.match(html, /Owner policy is not confirmed/);
  assert.doesNotMatch(html, /<pre/);
});
test("source/model HTML stays inert and bidi/control text is visibly escaped", () => {
  const record = view();
  const payload = '<script>alert("never")</script>\u202e\u001b';
  record.assessment = { status: "unknown", rationale: payload, assumptions: [], uncertainties: [], limitations: [] };
  record.failure = { stage: payload, code: "scripted-failure", turn_start: null };
  const html = render(record);
  assert.doesNotMatch(html, /<script>|\u202e|\u001b/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /\\u202e\\u001b/);
  assert.equal(visibleText("line1\nline2\t\r"), "line1\nline2\t\\u000d");
});
