<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/RESULT_VIEWER.md">한국어</a>
</p>

# Local workflow result viewer

[Documentation index](../README.md) · [Generated file workflow](GENERATED_FILE_WORKFLOW.md)

The source dashboard displays an explicitly selected generated-file workflow JSON and the existing
static route inventory. It runs locally; website deployment is unnecessary. Sharing, decisions,
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

1. Prepare the final stdout JSON from an already completed
   `codex-generate --file-workflow --json` invocation. Plans and interaction use stderr. When
   separately running that effectful workflow, use a private output file with `umask 077` and
   redirect only stdout. Viewing an existing result requires no new model request.
2. Choose the workflow result file in the dashboard. A rejected import clears the previous result.
   The English/Korean selector changes interface labels; source, diff and model text stay as recorded.
3. Inspect the summary, stage decisions, generated test, exact diff, before/after comparisons,
   failures and current copy/recovery state. A past after observation does not describe the current
   restored-before file.

Only `codex-generated-file-workflow` records are supported. New source CLI records declare
`schema_version: "1.0"` and bound `source_evidence`. Older records without the top-level version are
labeled `legacy-unversioned`; missing before source and declarations stay unavailable. Static scan
JSON, registered-template results, previews and arbitrary JSON are not converted into genuine
generation evidence.

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
