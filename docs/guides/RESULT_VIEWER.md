<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/RESULT_VIEWER.md">한국어</a>
</p>

# Local workflow result viewer

[Documentation index](../README.md) · [Generated file workflow](GENERATED_FILE_WORKFLOW.md)

The source dashboard displays an explicitly selected owner-read or generated-file workflow JSON and
the existing static route inventory. It runs locally; website deployment is unnecessary. Sharing, decisions,
generated-code execution, application and recovery remain in the CLI.

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
`authzest ui --help` lists `--host`, `--port`, `--reload` and `--workspace`. The workspace fixes the
static scan root, not a result directory. Rebuild the frontend after UI source changes. This route
uses an editable source install so the API can find `frontend/dist`; wheels and native scan/preview
binaries are not advertised as complete active-workflow/UI installers.

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
