<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/RESULT_VIEWER.md">한국어</a>
</p>

# Local workflow result viewer

[Documentation index](../README.md) · [Generated file workflow](GENERATED_FILE_WORKFLOW.md)

The source dashboard displays an explicitly selected owner-read or generated-file workflow JSON and
the existing static route inventory. It runs locally; website deployment is unnecessary. Ordinary
launches remain read-only. The explicit owner-read mode below connects the same engine used by the
CLI to separate current GUI decisions for sharing, execution, copy application and recovery.

## Supported source installation

Run these commands from the source checkout with Python 3.12 and npm available:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
cd frontend
npm ci
npm run build
cd ..
.venv/bin/authzest ui --workspace .
```

Open `http://127.0.0.1:8000`. Keep the server running; Ctrl-C stops it.
`authzest ui --help` lists `--host`, `--port`, `--reload`, `--workspace` and `--ai-runtime-config`. The workspace fixes the
static scan root, not a result directory. Rebuild the frontend after UI source changes. This route
uses an editable source install so the API can find `frontend/dist`; wheels and native scan/preview
binaries are not advertised as complete active-workflow/UI installers.

## Run the local AI workflow

This optional mode supports the maintained owner's archived-note scenario on a POSIX non-frozen
Python source installation. It uses the existing Codex ChatGPT login and the reviewed local
owner-read Docker runtime. It does not accept arbitrary repositories or apply to the original
checkout. First prepare and review the private runtime configuration and image using the
[owner-read contract](../development/GENERATED_REPAIR_CONTRACT.md#running-the-approved-copy-workflow).
Use its absolute local profile path at server startup:

```bash
.venv/bin/authzest ui --workspace . --ai-runtime-config /ABSOLUTE/PRIVATE/runtime.json
```

The server requires numeric loopback `127.0.0.1`, one app instance and no reload in this mode.
Open the private launch URL printed by the CLI. Its `authzest-ai` fragment contains a fresh launch
capability. The page removes that fragment and keeps the token only in memory. Do not publish the
launch URL. Ordinary `http://127.0.0.1:8000` access and saved-result imports do not acquire active
authority. Use the same-origin built dashboard; the Vite development proxy is not an active-origin
exception. After a page refresh, reopen the private launch URL to reconnect to the current in-memory
run. Restarting the server invalidates that capability and does not resume old operations.

1. Open the AI workflow and optionally check the installed Codex version/login readiness. The check
   shows coarse status, not account details, and makes no model request. There is no new OAuth login
   page or API-key form; use the existing Codex login.
2. Enter the exact model identifier and start one run. Starting does not approve source sharing.
3. Read each complete current plan and type the displayed exact phrase separately for runtime,
   sharing, copy, before, diff, apply, after and restore. Decisions are single-use, retain the core's
   original maximum 300 seconds and cannot be supplied in advance. Decline or cancel as appropriate.
4. Follow the bounded host activity and review the generated code, test, host-derived diff,
   before/after observations and recovery. Activity is not a model token stream. No-change, unknown
   and refused results do not allocate a copy or imply a successful repair.
5. Download the complete final JSON with the browser's save/download control and choose a familiar
   private location. The API accepts no server save path. Keep the JSON and any reported private
   copy/recovery files for inspection. A projection failure leaves the recorded display unavailable;
   it does not replace the result with success or erase the bounded downloadable JSON.

The controller admits one current run and retains one finished result. A new run can replace only
a run whose owned worker has ended. Download an available result before starting another. Polling does not approve decisions,
and closing a browser does not stop or restart its worker. The current plan is bounded to 2 MiB,
the final JSON to 4 MiB and activity to 256 events. Saved-result import below has a separate 512 KiB
limit, so a larger downloadable result is not guaranteed to reimport through that route.

Stop requests are cooperative. A running request or guest may need its existing timeout and cleanup
before the engine reaches a safe stopping point; `stopping` is not confirmation that it has ended.
Cancelling after application can leave recovery required and does not automatically restore.
Declining the after check with an empty answer may offer a fresh restore decision when the core
permits it. Complete that separate decision to restore. Unknown cleanup, stale input and user edits
remain visible and must not be bypassed. A finished job is not itself a verified fix.

The interactive route is tracked in [#189](https://github.com/casing1/authzest/issues/189).
Offline/mock checks of this bridge do not constitute a new installed live-Codex/guest observation,
release acceptance or permission to reuse a previous execution decision.

## Import an existing result

1. Prepare the final stdout JSON from an `owner-read-suggest --file-workflow --runtime-config … --json`
   invocation that you have already reviewed and run. Plans and interaction use stderr. Save stdout
   in a private file with `umask 077`. Runtime preparation and the sharing, copy, before, diff, apply,
   after and restore decisions are covered in the workflow contract. [Owner-read workflow contract](../development/GENERATED_REPAIR_CONTRACT.md#running-the-approved-copy-workflow)
2. Choose that result file in the dashboard. A rejected import clears the previous result.
   The English/Korean selector changes interface labels. Source, diff and model text stay as recorded.
3. Inspect the summary, stage decisions, source, generated regression, exact diffs, before/after
   comparisons and restoration or recovery requirements. The after column describes the tested copy
   before restoration.

Opening a saved result uses the selected bytes and requires no new model request. A complete current
owner-read result uses `kind: "owner-read-suggestion"` and `schema_version: "1.0"`. The viewer also
accepts suggestion-only, refusal and incomplete records with their available observations. Before
source and policy are shown when included in the selected record. Older owner-read records without
that source evidence display an unavailable warning.

The maintained archived-note case displays these expected values.

| Phase  | Owner's archived note | Pytest regression        | Intended policy matches |
| ------ | --------------------- | ------------------------ | ----------------------- |
| Before | HTTP 403              | Assertion failed, exit 1 | 6/7                     |
| After  | HTTP 200              | Passed, exit 0           | 7/7                     |

The separate expected-profile count can be 7/7 in both phases. Before compares the observed defective
baseline with its expected baseline responses. Intended-policy matches show how many of the seven
observations satisfy the target policy. Check restoration and recovery state alongside these counts.
A restored copy contains the original source bytes. A recovery-required record keeps that condition
visible even when an earlier after observation passed.

The older `codex-generated-file-workflow` import remains supported. Its version 1.0 records include
bound `source_evidence`. Older records without the top-level version carry `legacy-unversioned` and
leave missing before source and declarations unavailable. Static scan JSON, registered-template
results, previews and arbitrary JSON have their own formats and are rejected by this workflow importer.

## Import boundary and interpretation

The file chooser sends selected bytes to the local API's `POST /api/results/preview`. Browser and
API limit the file to **512 KiB**. The API checks bounded JSON shape and supported version, then
returns an `authzest-workflow-view` projection with schema `1.0` and provenance `imported-unverified`.
It accepts no filesystem path and does not save the import, follow receipt directories, run
commands, contact a model or apply patches. Do not upload private records to a hosted viewer.

Source, test, diff and explanations are untrusted text, rendered without HTML or Markdown execution.
The projection omits local workspace/evidence paths, runtime profiles, account/usage metadata and
execution IDs. This is not a general-purpose redaction tool: selected source and model text may
themselves contain sensitive information. Original JSON and raw phase captures remain in their
existing private locations; the viewer neither retrieves nor authenticates them.

An import displays what the record claims. Completion, approved decisions, test exit values and
matching finite controls are not a security pass, new permission or authenticated execution proof.
Unknown, not-run, declined, unsupported, failed and recovery-required states remain distinct.
Before/after counts refer to maintained finite controls; generated test reports remain auxiliary.
The viewer does not establish real authentication, resource enforcement, isolation or a generally
verified repair. Opening a record cannot resume a session or reuse approval.
