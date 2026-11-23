# Course demonstration and evidence

[한국어](../i18n/ko/guides/COURSE_DEMO.md) · [Documentation](../README.md) · [Course delivery #85](https://github.com/casing1/authzest/issues/85)

Use the local AI workspace to present the maintained owner's archived-note scenario: review a new
regression test and rule change, inspect the before/after observations, and confirm restoration.
The GUI and CLI use the same owner-read engine and separate current decisions. Use the same
checkout throughout the demonstration and download its result before starting another run.

This guide describes current source functionality. Source package version `0.1.0` is preparation for
the course release; the latest published release remains
[alpha.4](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.4). Public delivery and mock tests
are not acceptance of a new installed candidate. Keep the historical evidence below tied to its
recorded source and provenance.

## Current owner-read demonstration

### Prepare the source installation

Active AI controls require a POSIX non-frozen, editable source checkout, Python 3.12, the UI extra
and built frontend assets. Use Node.js 22.13 or later in the 22.x line, or Node.js 24.
Wheels and standalone scan/preview binaries are not complete active-GUI installers.
Run from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/authzest scan examples/fastapi_inventory
```

The inventory example contains four Python files and three route registrations. This is static
source evidence. The GUI's workspace selects only the static scan root; it does not select an
arbitrary repository for AI repair. The AI workflow uses the packaged synthetic archived-note
source and policy.

Prepare and review the local Docker image and private runtime configuration through the
[owner-read workflow contract](../development/GENERATED_REPAIR_CONTRACT.md#running-the-approved-copy-workflow).
Keep the reviewed Docker runtime running. Existing Codex ChatGPT login is reused; no API-key form
or new OAuth login page is provided. The current adapter requires a trusted Codex CLI `0.153.0`.
Runtime/source sharing and execution have their own current
plans and decisions.

### Open the active GUI

Replace the placeholder with the absolute path of your reviewed private runtime configuration.
The default address is numeric loopback `127.0.0.1:8000`; this mode requires one process and no reload.

```bash
.venv/bin/authzest ui --workspace examples/fastapi_inventory --ai-runtime-config /ABSOLUTE/PRIVATE/runtime.json
```

Open the **complete private AI workspace URL printed in the terminal in a new browser tab**.
Its `authzest-ai` fragment carries a fresh launch capability; the page removes it and keeps it only
in memory. Keep this URL private and omit it from recordings. A plain dashboard URL grants no
active controls. After a page refresh, reopen the complete launch URL; restarting the server creates
a different capability. Use the built same-origin dashboard, not the Vite development proxy.

### Present the decisions and result

1. In **AI repair**, optionally check existing login and CLI compatibility, then enter the exact
   reviewed model identifier and prepare a run. Coarse login status does not establish model access.
2. Review the complete current runtime plan, then its separate source-sharing preview. Preparing a
   run alone does not approve either step.
3. Review and enter each displayed exact phrase in order:
   `runtime → share → copy → before → diff → apply → after → restore`. Each decision is fresh,
   single-use and expires within the original maximum 300 seconds. There is no advance approval or
   old-decision replay. Decline a step when its current plan is not acceptable.
4. Show the source and declared policy, model-authored regression test and proposed replacement,
   and host-derived exact source/test diffs. Explain the bounded host activity; it is not raw Codex
   logs or a stream of model tokens.
5. Compare the recorded checks and recovery in the table below. Inspect the semantic outcome,
   application state, cleanup and restoration rather than treating a finished host job as a fix.
6. Use **Download result JSON**. Find it in the browser download list, or use the browser's download
   settings to choose a familiar private folder. Save it before another run replaces the result or
   the server is closed. The API accepts no server save path.

| Phase  | Owner's archived note | Generated regression     | Intended policy matches |
| ------ | --------------------- | ------------------------ | ----------------------- |
| Before | HTTP 403              | Assertion failed, exit 1 | 6/7                     |
| After  | HTTP 200              | Passed, exit 0           | 7/7                     |

These are the maintained scenario's expected values, not prefilled observations for a new run.
Expected-profile matches can be 7/7 in both phases because the baseline profile expects its false
denial. Intended-policy matches show the correction from 6/7 to 7/7. The after column describes the
copy before restoration; verify `restored-before` and that recovery is not required. Unknown,
declined, not-run, failed and recovery-required records retain their available evidence and state.

Session polling stops after `finished` or `failed`; active, waiting and stopping states still update.
Starting a new active run resumes updates. Closing the browser does not stop the worker. Stop is
cooperative and may leave an applied copy requiring recovery; it does not approve restoration.
When the core offers a separate restore plan, review and decide it separately. The current launch
link can reconnect to the current in-memory run without extending its decisions. Importing a saved
result or restarting the server cannot replay a decision or resume an old file session.

### Read-only display or CLI alternative

For static scanning and importing an existing result, start the ordinary read-only dashboard:

```bash
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

Select a final JSON you are authorized to view. Import supports `owner-read-suggestion` version 1.0
and the historical generated-file format below, up to **512 KiB**. The local API labels the display
`imported-unverified`: it shows the record's claims and reads no referenced runtime, copy or log
paths. The active GUI's final download can be up to **4 MiB**, so not every downloadable result can
be reimported. Keep full JSON and raw captures private. [Result viewer guide](RESULT_VIEWER.md)

The CLI offers the same owner-read engine. Review its complete offline preview first:

```bash
.venv/bin/authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --preview-only
```

After reviewing that scope, this command runs the interactive workflow and prints the location of
its final stdout JSON. Replace the model and runtime path with the reviewed values. Keep the
terminal open: runtime, sharing and all six file-stage plans/prompts use stderr and need their own
current decisions.

```bash
(
  umask 077
  demo_result_dir=$(mktemp -d) || exit 1
  demo_result_status=0
  .venv/bin/authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --json > "$demo_result_dir/owner-read-result.json" || demo_result_status=$?
  printf '%s\n' "$demo_result_dir/owner-read-result.json"
  exit "$demo_result_status"
)
```

### Evidence and presentation limits

[#190](https://github.com/casing1/authzest/pull/190) delivers the opt-in GUI and
[#192](https://github.com/casing1/authzest/pull/192) stops terminal-state polling. Their offline and
mocked checks cover the UI bridge; they do not establish a new actual model/guest observation or
stable acceptance. Use only invocation evidence you are authorized to present, with its own source
revision, provenance and limits. Never publish private launch URLs, account details, raw logs or
local result/copy paths in a screen recording.

The public maintained-fixture proof used a maintainer-authored proposal and four real isolated
Linux guests. It observed the expected before assertion failure, applied the exact change only to
a fresh copy, observed the passing after test and all seven intended controls, restored the original
source bytes and removed all four guests. This proof is separate from model generation and GUI
acceptance. [Maintained-fixture proof #187](https://github.com/casing1/authzest/pull/187)

## Historical alpha.4 walkthrough

The archived alpha.4 walkthrough uses source commit [`c454628`](https://github.com/casing1/authzest/commit/c45462889fcbfa5b8354558336f6d4bd1540c27d)
(`0.1.0a4` package metadata) and one previously recorded run of the maintained ownership exercise.
The recorded submission target at that time was around November 18, 2026.

### Install and open the dashboard

On macOS or Linux, use Python 3.12 and Node.js 22.13 or later in the 22.x line, or Node.js 24.
To reproduce the recorded installation, start from a separate checkout at the stated revision.

```bash
git clone https://github.com/casing1/authzest.git authzest-course
cd authzest-course
git switch --detach c45462889fcbfa5b8354558336f6d4bd1540c27d
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/authzest scan examples/fastapi_inventory
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

Open [the local dashboard](http://127.0.0.1:8000). The packaged inventory example reports four
Python files and three route registrations. The fresh-install walkthrough used macOS arm64,
Python 3.12.7 and Node.js 24.11.0. Windows CI covers portable CLI and result contracts.
See the [result viewer guide](RESULT_VIEWER.md) for asset builds and the import format.

### Demonstrate an existing run

1. Show the static inventory and explain that it lists source declarations.
2. Open the final CLI result JSON you have permission to view. The historical record has a
   `legacy-unversioned` label. Its original source and declarations are unavailable in the import.
3. Show the generated test, proposed diff, recorded decisions, both comparison summaries and
   `restored-before`. The after column describes the tested copy before restoration.
4. Show a rejected input in the terminal and in the viewer using the example below. Explain why
   the rows for execution, application and recovery have no observations.

The viewer accepts selected JSON up to 512 KiB and labels it `imported-unverified`. It will open the
saved record without a provider call or worker run. If you lack the original result, present the
aggregate evidence below and use the refusal record for the interactive part. Keep raw captures and
account, runtime and path information private.

The previous exercise used one maintained FastAPI ownership scenario with in-memory data and a
demo actor header. The header does not authenticate a user. Comparisons cover that policy and
its maintained finite controls. The active workflow has separate requirements for a non-frozen POSIX
installation and reviewed Linux runtime images. The [generated file workflow](GENERATED_FILE_WORKFLOW.md)
describes its scope and approval stages.

### Show an early refusal

The command deliberately omits the required runtime profile. It exits `2` before model sharing,
runtime startup or workspace changes. Open the printed file path in the viewer.

```bash
(
  umask 077
  demo_dir=$(mktemp -d) || exit 1
  refusal_status=0
  .venv/bin/authzest codex-generate --model course-demo --file-workflow --json > "$demo_dir/refused.json" || refusal_status=$?
  if [ "$refusal_status" -ne 2 ]; then
    printf 'Expected refusal exit 2, received %s\n' "$refusal_status" >&2
    exit 1
  fi
  printf '%s\n' "$demo_dir/refused.json"
)
```

Expect `invalid-input`, `not-run`, zero adapter attempts and unavailable before/after observations.
Portable CI also exercises stale decisions and refusal to overwrite edited bytes through local
regression fixtures. Keep that coverage distinct from the live observation below.

### Evidence to cite

| Scope                                                                                                                                                                          | Observation and limit                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Historical installed run at [`34baebc`](https://github.com/casing1/authzest/commit/34baebc), same tree as [#172 merge `ad4dea7`](https://github.com/casing1/authzest/pull/172) | A live adapter returned a proposed test and source change. The generated test exit was 1 before and 0 after. Independent controls matched 17/17 cases and 21/21 requests in each phase against that phase's expected profile. The approved change was applied only to a copy, which was restored to its original bytes. Cleanup was confirmed and checkout bytes were preserved. |
| Local viewer at [`c454628` / #173](https://github.com/casing1/authzest/pull/173)                                                                                               | Browser verification opened the historical record and separately displayed a version 1.0 refusal. Version 1.0 success and source fields have fixture coverage. A new version 1.0 live success on this revision is unrecorded.                                                                                                                                                    |
| [PR CI](https://github.com/casing1/authzest/actions/runs/44273783577) and [merged CI](https://github.com/casing1/authzest/actions/runs/44276437537)                            | 8,712 Python tests passed and the Windows job reported 3,037 passed with 422 skipped on the reviewed PR. The merged jobs passed, including the [CodeQL analysis](https://github.com/casing1/authzest/actions/runs/44276438312).                                                                                                                                                  |
| [Independent evaluation #84](https://github.com/casing1/authzest/issues/84)                                                                                                    | Independent comparative evidence is unavailable for this submission. The reported phases measure finite workflow behavior and leave authorization assurance unknown.                                                                                                                                                                                                             |

Stable acceptance remains tracked in [#150](https://github.com/casing1/authzest/issues/150),
with installed acceptance follow-up in [#151](https://github.com/casing1/authzest/issues/151) and
[#152](https://github.com/casing1/authzest/issues/152). Published alpha.4 artifacts are historical
release evidence. The candidate-specific tooling decisions in
[#89](https://github.com/casing1/authzest/issues/89) and
[#171](https://github.com/casing1/authzest/issues/171) remain separate.
