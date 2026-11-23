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
fs.mkdirSync(path.join(frontend, "node_modules/.tmp"), { recursive: true });
const build = fs.mkdtempSync(path.join(frontend, "node_modules/.tmp/repair-tests-"));
after(() => fs.rmSync(build, { recursive: true, force: true }));
for (const name of ["viewer-types.ts", "viewer-text.ts", "WorkflowResult.tsx", "ResultViewer.tsx", "ScanPanel.tsx", "repair-types.ts", "repair-client.ts", "repair-text.ts", "RepairPanel.tsx", "App.tsx"]) {
  const output = ts.transpileModule(fs.readFileSync(path.join(frontend, "src", name), "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX },
  });
  fs.writeFileSync(path.join(build, name.replace(/\.tsx?$/, ".js")), output.outputText);
}
const load = name => import(pathToFileURL(path.join(build, name)));
const { default: App } = await load("App.js");
const { default: RepairPanel, RepairPlan, RepairStatus } = await load("RepairPanel.js");
const { repairMessages } = await load("repair-text.js");
const client = await load("repair-client.js");
const { activeRepair } = await load("repair-types.js");
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const secret = "p".repeat(43);

function pending(stage = "copy") {
  return {
    prompt_id: "prompt-123", stage, prompt: `Type '${stage} owner-read-stage-123' to approve this stage, or press Enter to decline: `,
    remaining_seconds: 290,
    plan: {
      kind: "owner-read-file-stage-plan", stage,
      inputs: {
        request: { source: { path: "src/authzest/owner_read_demo/availability.py", text: 'def available_to_owner(state):\n    return state == "active"\n' }, policy: ["An authenticated owner can read their archived note."] },
        proposal: { rationale: "Permit the owner's archived note.", source: 'def available_to_owner(state):\n    return state in ("active", "archived")\n', test: 'def test_owner_archive(owner_client):\n    assert owner_client.get("/records/archived-note").status_code == 200\n' },
        diffs: [{ path: "src/authzest/owner_read_demo/availability.py", diff: '-    return state == "active"\n+    return state in ("active", "archived")\n' }],
      },
    },
  };
}
function run() {
  return {
    run_id: "run-123", revision: 3, state: "waiting",
    events: [{ sequence: 1, stage: "runtime", status: "awaiting-decision" }],
    pending: pending(), view: null, view_error: null, result_available: false, failure: null, cancel_requested: false,
  };
}

test("repair interface labels have nonempty English and Korean counterparts", () => {
  assert.deepEqual(Object.keys(repairMessages.en).sort(), Object.keys(repairMessages.ko).sort());
  for (const language of ["en", "ko"]) for (const value of Object.values(repairMessages[language])) assert.ok(value.trim());
});
test("default app retains results and does not claim an active authenticated run", () => {
  const html = render(App, {});
  assert.match(html, /No result loaded/);
  assert.match(html, /AI repair/);
  assert.doesNotMatch(html, /Authenticated|Run ended|7 \/ 7/);
});
test("launch token chooses the AI view but never renders the capability", () => {
  const html = render(App, { initialAIToken: secret });
  assert.match(html, /Prepare AI repair/);
  assert.match(html, /packaged owner \/ archived-note/);
  assert.doesNotMatch(html, new RegExp(secret));
  assert.match(html, /Not checked/);
});
test("disabled operator view explains explicit launch and disables actions", () => {
  const html = render(RepairPanel, { language: "en", health: "online", token: null });
  assert.match(html, /Active AI controls are disabled/);
  assert.match(html, /--ai-runtime-config/);
  assert.match(html, /type="submit" class="primary" disabled=""/);
  assert.doesNotMatch(html, /Authenticated|7 \/ 7|Run ended/);
  const ko = render(RepairPanel, { language: "ko", health: "online", token: null });
  assert.match(ko, /AI 실행 기능이 활성화되지 않았습니다/);
  assert.match(ko, /기존 로그인 확인/);
});
test("rendering an active view performs no model, account or mutation request", () => {
  const previous = globalThis.fetch;
  const calls = [];
  globalThis.fetch = (...args) => { calls.push(args); throw new Error("Unexpected fetch during rendering"); };
  try { render(RepairPanel, { language: "en", health: "online", token: secret }); }
  finally { globalThis.fetch = previous; }
  assert.deepEqual(calls, []);
});
test("current plan renders source, generated test and exact diffs with policy", () => {
  const html = render(RepairPlan, { language: "en", pending: pending() });
  for (const text of [/Original source/, /Proposed replacement/, /Generated defensive test/, /Exact proposed changes/, /Declared policy/, /Complete current plan/, /test_owner_archive/]) assert.match(html, text);
  const ko = render(RepairPlan, { language: "ko", pending: pending() });
  for (const text of [/원본 소스/, /수정 제안 소스/, /현재 전체 계획/, /명시한 정책/]) assert.match(ko, text);
});
test("provider text in current plans is inert and control characters are escaped", () => {
  const p = pending();
  p.plan.inputs.proposal.rationale = '<script>alert("never")</script>\u202e\u001b';
  p.plan.inputs.proposal.source = '<img src=x onerror="never">';
  const html = render(RepairPlan, { language: "en", pending: p });
  assert.equal(html.toLowerCase().includes("<script"), false);
  assert.equal(html.includes("<img"), false);
  assert.equal(html.includes("\u202e"), false);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /\\u202e\\u001b/);
});
test("runtime approval shows the declared image, platform and fixed limits", () => {
  const p = pending("runtime");
  p.plan = { runtime: { profile: { image_id: "sha256:maintained-test-image", platform: "linux/arm64" } }, scope: { network: "none", phase_seconds: 40, cleanup_seconds: 10 } };
  const en = render(RepairPlan, { language: "en", pending: p });
  assert.match(en, /Reviewed local runtime/);
  assert.match(en, /sha256:maintained-test-image/);
  assert.match(en, /linux\/arm64/);
  assert.match(en, /40 \/ 10/);
  assert.match(render(RepairPlan, { language: "ko", pending: p }), /검토할 로컬 런타임/);
});
test("host lifecycle completion does not invent a successful repair", () => {
  const r = run(); r.state = "finished"; r.pending = null;
  const html = render(RepairStatus, { language: "en", run: r });
  assert.match(html, /Run ended/);
  assert.match(html, /not a stream of model tokens/);
  assert.doesNotMatch(html, /7 \/ 7|security pass|repair successful/);
  assert.equal(activeRepair(r), false);
  r.state = "stopping";
  assert.equal(activeRepair(r), true);
});
test("recovery warning remains visible even after the host job ends", () => {
  const r = run(); r.state = "finished";
  r.view = { summary: { recovery_required: true } };
  assert.match(render(RepairStatus, { language: "en", run: r }), /Recovery remains required/);
  assert.match(render(RepairStatus, { language: "ko", run: r }), /복구가 여전히 필요합니다/);
});

test("fragment bootstrap removes the capability before React with no storage or query transport", () => {
  const calls = [];
  const history = { replaceState: (...args) => calls.push(args) };
  const value = client.takeRepairLaunchToken({ hash: `#authzest-ai=${secret}`, pathname: "/", search: "" }, history);
  assert.equal(value, secret);
  assert.deepEqual(calls, [[null, "", "/"]]);
  assert.equal(client.takeRepairLaunchToken({ hash: "", pathname: "/", search: `?authzest-ai=${secret}` }, history), null);
});
test("duplicate or malformed launch fragments stay locked and are stripped", () => {
  for (const hash of [`#authzest-ai=${secret}&authzest-ai=${secret}`, "#authzest-ai=short", "#authzest-ai=%3Cscript%3E"]) {
    const calls = [];
    assert.equal(client.takeRepairLaunchToken({ hash, pathname: "/", search: "" }, { replaceState: (...args) => calls.push(args) }), null);
    assert.deepEqual(calls, [[null, "", "/"]]);
  }
  assert.equal(client.takeRepairLaunchToken({ hash: `#authzest-ai=${secret}`, pathname: "/", search: "" }, { replaceState: () => { throw new Error("Unavailable"); } }), null);
});
test("bootstrap preserves unrelated location state while removing only the capability", () => {
  const calls = [];
  assert.equal(client.takeRepairLaunchToken({ hash: `#view=result&authzest-ai=${secret}`, pathname: "/", search: "?lang=ko" }, { replaceState: (...args) => calls.push(args) }), secret);
  assert.deepEqual(calls, [[null, "", "/?lang=ko#view=result"]]);
});
test("snapshot validation rejects malformed deadlines, events and result markers", () => {
  assert.equal(client.isRepairRun(run()), true);
  for (const mutate of [r => { r.revision = -1; }, r => { r.state = "success"; }, r => { r.pending.remaining_seconds = Infinity; }, r => { r.pending.remaining_seconds = 301; }, r => { r.pending.stage = "shell"; }, r => { r.events[0].sequence = true; }, r => { r.result_available = "yes"; }, r => { r.view = { kind: "arbitrary" }; }]) {
    const r = run(); mutate(r); assert.equal(client.isRepairRun(r), false);
  }
});

test("API client uses capability headers, JSON decisions and never a token URL", async () => {
  const previous = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    return new Response(JSON.stringify(url === "/api/ai/session" ? { run: null } : run()), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    assert.equal(await client.getRepairSession(secret), null);
    await client.startRepair(secret, "gpt-6-astra");
    await client.decideRepair(secret, "run-123", "prompt-123", "copy owner-read-stage-123");
    await client.cancelRepair(secret, "run-123");
  } finally { globalThis.fetch = previous; }
  assert.deepEqual(calls.map(row => row[0]), ["/api/ai/session", "/api/ai/runs", "/api/ai/runs/run-123/decisions", "/api/ai/runs/run-123/cancel"]);
  for (const [url, options] of calls) {
    assert.equal(url.includes(secret), false);
    assert.equal(options.headers["X-AuthZest-Token"], secret);
    assert.equal(options.credentials, "omit");
    assert.equal(options.cache, "no-store");
    assert.equal(options.redirect, "error");
  }
  assert.deepEqual(JSON.parse(calls[2][1].body), { prompt_id: "prompt-123", answer: "copy owner-read-stage-123" });
  assert.equal(calls[2][1].headers["Content-Type"], "application/json");
});
test("decline stays empty and API errors never echo private response bodies", async () => {
  const previous = globalThis.fetch;
  let options;
  globalThis.fetch = async (_url, incoming) => { options = incoming; return new Response("PRIVATE-DO-NOT-ECHO", { status: 409 }); };
  try {
    await assert.rejects(client.decideRepair(secret, "run-123", "prompt-123", ""), error => error instanceof client.RepairAPIError && error.status === 409 && !error.message.includes("PRIVATE"));
  } finally { globalThis.fetch = previous; }
  assert.equal(JSON.parse(options.body).answer, "");
});
test("API client rejects unexpected session data without constructing a fake run", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ run: { state: "completed" } }), { headers: { "Content-Type": "application/json" } });
  try { await assert.rejects(client.getRepairSession(secret), client.RepairAPIError); }
  finally { globalThis.fetch = previous; }
});
test("account diagnostics expose only supported coarse fields", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ codex_status: "authenticated", version_status: "supported", model_access: "not-checked", account_email: "PRIVATE" }), { headers: { "Content-Type": "application/json" } });
  try {
    const value = await client.inspectRepairAccount(secret);
    assert.equal(value.codex_status, "authenticated");
    assert.deepEqual(Object.keys(value).sort(), ["codex_status", "model_access", "version_status"]);
  } finally { globalThis.fetch = previous; }
});
test("JSON download is an authenticated Blob with bounded JSON media type", async () => {
  const previous = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, options) => { request = [url, options]; return new Response('{"kind":"owner-read-suggestion"}', { headers: { "Content-Type": "application/json" } }); };
  try { assert.match(await (await client.downloadRepairResult(secret, "run-123")).text(), /owner-read-suggestion/); }
  finally { globalThis.fetch = previous; }
  assert.equal(request[0], "/api/ai/runs/run-123/result");
  assert.equal(request[1].headers["X-AuthZest-Token"], secret);
});
test("unsafe run path and non-JSON download are refused", async () => {
  const previous = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; return new Response("<html>private</html>", { headers: { "Content-Type": "text/html" } }); };
  try {
    await assert.rejects(client.downloadRepairResult(secret, "../other"), client.RepairAPIError);
    assert.equal(calls, 0);
    await assert.rejects(client.downloadRepairResult(secret, "run-123"), client.RepairAPIError);
    assert.equal(calls, 1);
  } finally { globalThis.fetch = previous; }
});
