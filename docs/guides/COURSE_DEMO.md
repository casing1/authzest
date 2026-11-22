# Course demonstration and evidence

[한국어](../i18n/ko/guides/COURSE_DEMO.md) · [Documentation](../README.md) · [Course delivery #85](https://github.com/casing1/authzest/issues/85)

The current demonstration follows the synthetic owner's archived-note workflow. Show the saved CLI
result in the local dashboard, then explain the proposed change, the before/after observations and
the restoration state. Use the same checkout and saved result throughout the demonstration.
Prepare the reviewed Docker image, private runtime configuration and individual decisions through
the workflow contract. [Workflow contract](../development/GENERATED_REPAIR_CONTRACT.md#running-the-approved-copy-workflow)

## Current owner-read demonstration

Build and start the local UI from the checkout used for the demonstration.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

Use Python 3.12 and Node.js 22.13 or later in the 22.x line, or Node.js 24. Open
[the local dashboard](http://127.0.0.1:8000). The packaged inventory example supplies four Python files
and three route registrations. The workspace selects the static inventory root. Workflow import
uses the bytes of the result file you select.

If you already have a result you are authorized to view, select its final JSON in the dashboard.
Prepare a new result by reviewing the complete offline preview for your exact model and private
runtime configuration.

```bash
.venv/bin/authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --preview-only
```

After reviewing that scope, the following command runs the interactive workflow and saves its final
stdout JSON in a fresh private directory. Runtime and sharing prompts, followed by copy, before,
exact diff, apply, after and restore decisions, use stderr. Replace the model and runtime path with
the values you reviewed. Keep the terminal open for those decisions.

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

Walk through the imported result in this order.

1. The suggestion summary, source evidence when available, generated regression and exact source/test diffs.
2. The six file-stage decisions and the source application state.
3. Before HTTP 403, the failed regression assertion and intended-policy matches of 6/7.
4. After HTTP 200, the passing regression and intended-policy matches of 7/7.
5. Restoration and recovery-required state. The after column records the copy before restoration.

Expected-profile matches can be 7/7 in each phase because each phase has its own expected responses.
Intended-policy matches show the correction from 6/7 to 7/7. Unknown, declined, not-run, failed and
recovery-required records retain their available evidence and state.

The public maintained-fixture proof used a maintainer-authored proposal and four real isolated Linux
guests. It observed the expected before
assertion failure, applied the exact change only to a fresh copy, observed the passing after test
and all seven intended controls, restored the original source bytes and removed all four guests.
A submission's own saved result should carry the provenance and limits of that invocation. [Maintained-fixture proof #187](https://github.com/casing1/authzest/pull/187)

The viewer supports `owner-read-suggestion` version 1.0 and the historical generated-file format below.
It accepts a selected file up to 512 KiB, projects it through the local API and labels it
`imported-unverified`. It displays the record's claims. It reads no referenced runtime, copy or log
paths. Keep the full JSON and raw captures private. The [result viewer guide](RESULT_VIEWER.md)
explains source availability, omitted fields and import limits.

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
