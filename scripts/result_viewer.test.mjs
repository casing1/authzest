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
for (const name of ["viewer-types.ts", "viewer-text.ts", "WorkflowResult.tsx", "ResultViewer.tsx", "ScanPanel.tsx", "repair-types.ts", "repair-text.ts", "repair-client.ts", "RepairPanel.tsx", "App.tsx"]) {
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
  const payload = '<script>alert("never")</script><SCRIPT>UPPER</SCRIPT>\u202e\u001b';
  record.assessment = { status: "unknown", rationale: payload, assumptions: [], uncertainties: [], limitations: [] };
  record.failure = { stage: payload, code: "scripted-failure", turn_start: null };
  const html = render(record);
  assert.equal(html.toLowerCase().includes("<script"), false);
  assert.equal(html.includes("\u202e"), false);
  assert.equal(html.includes("\u001b"), false);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /\\u202e\\u001b/);
  assert.equal(visibleText("line1\nline2\t\r"), "line1\nline2\t\\u000d");
});

function ownerReadView() {
  const record = view();
  record.record_kind = "owner-read-suggestion";
  record.summary = {
    ...record.summary, status: "proposed-change", exit_code: 0,
    proposal_status: "proposed-change", execution_status: "completed",
    patch_application: "applied-to-copy", current_copy_state: "restored-before",
    restoration_status: "restored", recovery_required: false,
  };
  const phase = before => ({
    candidate: before ? "before" : "after", status: "matched",
    test_exit_code: before ? 1 : 0, regression_status: before ? "assertion-failed" : "passed",
    response_status: before ? 403 : 200, cleanup_confirmed: true,
    generated_runtime_attempted: true, application_sha256: "a".repeat(64), test_sha256: "b".repeat(64),
    failure: null, transport_failure: null,
    comparison: {
      expected_profile: before ? "before" : "intended", comparison_status: "compared",
      matches_expected_profile: true, case_count: 7, matching_case_count: 7,
      intended_match_count: before ? 6 : 7, request_count: 7, matching_request_count: 7,
    },
  });
  record.session = {
    status: "completed", stopped_stage: null, closed: true, close_status: "closed",
    runtime_input_cleanup: null, cleanup_unconfirmed: false, clock_unconfirmed: false,
    workspace_state: "restored-before", stages: [], checks: { before: phase(true), after: phase(false) },
    authorization_status: null, verified_fix: null, isolation_established: null,
    resource_enforcement_established: null, test_report_authenticity: "imported-unverified",
  };
  record.proposal = {
    rationale: "Permit the owner's archived note.", assumptions: [], uncertainties: [], limitations: [],
    after_source: { path: "src/authzest/owner_read_demo/availability.py", sha256: "c".repeat(64), text: 'def available_to_owner(state: str) -> bool:\n    return state in ("active", "archived")\n' },
    test: { path: "tests/test_owner_archived_read.py", sha256: "b".repeat(64), text: 'def test_owner_archive(owner_client):\n    assert owner_client.get("/records/archived-note").status_code == 200\n' },
    changes: [{ path: "src/authzest/owner_read_demo/availability.py", before_sha256: "a".repeat(64), after_sha256: "c".repeat(64), diff: '-    return state == "active"\n+    return state in ("active", "archived")\n' }],
  };
  return record;
}

function phaseMarkup(html, title) {
  const match = html.match(new RegExp(`<article[^>]*><h3>${title}</h3>([\\s\\S]*?)</article>`));
  assert.ok(match, `Missing phase ${title}`);
  return match[1];
}

test("owner-read phases distinguish expected failure from intended policy matches", () => {
  const html = render(ownerReadView());
  const before = phaseMarkup(html, "Before"), after = phaseMarkup(html, "After");
  assert.match(before, /HTTP response status<\/dt><dd>403<\/dd>/);
  assert.match(before, /Pytest regression<\/dt><dd>assertion-failed<\/dd>/);
  assert.match(before, /Generated test exit code<\/dt><dd>1<\/dd>/);
  assert.match(before, /Expected profile matches<\/dt><dd>7 \/ 7<\/dd>/);
  assert.match(before, /Intended policy matches<\/dt><dd>6 \/ 7<\/dd>/);
  assert.match(after, /HTTP response status<\/dt><dd>200<\/dd>/);
  assert.match(after, /Pytest regression<\/dt><dd>passed<\/dd>/);
  assert.match(after, /Generated test exit code<\/dt><dd>0<\/dd>/);
  assert.match(after, /Intended policy matches<\/dt><dd>7 \/ 7<\/dd>/);
  assert.match(html, /Recovery required<\/dt><dd>No<\/dd>/);
  assert.match(html, /Restoration<\/dt><dd>restored<\/dd>/);
  assert.match(html, /Imported record · authenticity not established/);
  assert.doesNotMatch(before, /Matching requests/);
});

test("owner-read evidence and recovery labels render in Korean", () => {
  const html = render(ownerReadView(), "ko");
  const before = phaseMarkup(html, "수정 전 · Before");
  assert.match(before, /HTTP 응답 상태<\/dt><dd>403<\/dd>/);
  assert.match(before, /pytest 회귀 테스트<\/dt><dd>assertion-failed<\/dd>/);
  assert.match(before, /기대 프로필 일치 사례<\/dt><dd>7 \/ 7<\/dd>/);
  assert.match(before, /의도한 정책 일치<\/dt><dd>6 \/ 7<\/dd>/);
  assert.match(html, /복구 필요<\/dt><dd>아니요<\/dd>/);
  assert.match(html, /가져온 기록 · 진위 미확립/);
});

test("owner-read recovery remains visible independently of successful earlier checks", () => {
  const record = ownerReadView();
  record.summary.exit_code = 1;
  record.summary.restoration_status = "required";
  record.summary.recovery_required = true;
  record.summary.current_copy_state = "applied-after";
  record.session.checks.after = null;
  const html = render(record);
  assert.match(html, /Recovery required<\/dt><dd>Yes<\/dd>/);
  assert.match(html, /Restoration<\/dt><dd>required<\/dd>/);
  assert.match(html, /No phase receipt/);
  assert.match(html, /authenticity not established/);
});

test("older owner-read records keep missing evidence unavailable", () => {
  const record = ownerReadView();
  delete record.summary.recovery_required;
  const before = record.session.checks.before;
  delete before.regression_status;
  delete before.response_status;
  delete before.comparison.intended_match_count;
  record.session.checks.after = null;
  const html = render(record);
  const phase = phaseMarkup(html, "Before");
  assert.match(phase, /HTTP response status<\/dt><dd>Unknown \/ not reported<\/dd>/);
  assert.match(phase, /Intended policy matches<\/dt><dd>Unknown \/ not reported<\/dd>/);
  assert.match(html, /Recovery required<\/dt><dd>Unknown \/ not reported<\/dd>/);
  assert.match(html, /Original source and declarations are unavailable/);
  assert.doesNotMatch(html, /0 \/ 7|0 \/ 0/);
});

test("an explicitly recorded zero policy match count remains zero", () => {
  const record = ownerReadView();
  record.session.checks.after.comparison.intended_match_count = 0;
  assert.match(phaseMarkup(render(record), "After"), /Intended policy matches<\/dt><dd>0 \/ 7<\/dd>/);
});

test("owner-read code, test and diff display their recorded paths", () => {
  const html = render(ownerReadView());
  assert.match(html, /availability\.py/);
  assert.match(html, /test_owner_archived_read\.py/);
  assert.match(html, /available_to_owner/);
  assert.match(html, /owner_client\.get/);
  assert.doesNotMatch(html, /test_generated_ownership\.py|· app\.py/);
});

test("legacy phase layout retains case and request comparisons without owner fields", () => {
  const record = ownerReadView();
  delete record.record_kind;
  delete record.summary.recovery_required;
  for (const phase of Object.values(record.session.checks)) {
    delete phase.regression_status;
    delete phase.response_status;
    delete phase.comparison.intended_match_count;
  }
  const html = render(record), before = phaseMarkup(html, "Before");
  assert.match(before, /Matching cases<\/dt><dd>7 \/ 7<\/dd>/);
  assert.match(before, /Matching requests<\/dt><dd>7 \/ 7<\/dd>/);
  assert.doesNotMatch(html, /HTTP response status|Intended policy matches|Recovery required/);
});

test("import instructions cover owner-read and generated workflows", () => {
  const html = renderToStaticMarkup(React.createElement(ResultViewer, { health: "online", language: "en" }));
  assert.match(html, /owner-read-suggest/);
  assert.match(html, /codex-generate/);
  assert.match(html, /--file-workflow --json/);
});

test("owner-read source evidence shows baseline and policy without an empty declaration section", () => {
  const record = ownerReadView();
  record.source_evidence = {
    scenario_id: "owner-archived-note", source: { path: "src/authzest/owner_read_demo/availability.py", sha256: "a".repeat(64), text: 'def available_to_owner(state: str) -> bool:\n    return state == "active"\n' },
    declarations: [], policy: ["Owners may read active and archived notes."], policy_authorship: "maintainer", policy_review: "reviewed",
  };
  const html = render(record);
  assert.match(html, /Original source snapshot · src\/authzest\/owner_read_demo\/availability\.py/);
  assert.match(html, /Owners may read active and archived notes/);
  assert.doesNotMatch(html, /<h3>Source declarations<\/h3>|Original source and declarations are unavailable/);
});

test("capture privacy copy describes the view rather than the selected JSON export", () => {
  assert.match(render(ownerReadView()), /not included in this view/);
  assert.doesNotMatch(render(ownerReadView()), /not included in this export/);
  assert.match(render(ownerReadView(), "ko"), /이 화면에는 테스트 원본 출력과 요청별 관찰값이 없습니다/);
});
