# Course demonstration and evidence

[한국어](../i18n/ko/guides/COURSE_DEMO.md) · [Documentation](../README.md) · [Course delivery #85](https://github.com/casing1/authzest/issues/85)

The demonstration uses source commit [`c454628`](https://github.com/casing1/authzest/commit/c45462889fcbfa5b8354558336f6d4bd1540c27d)
(`0.1.0a4` package metadata) and one previously recorded run of the maintained ownership exercise.
The course submission target is around November 18, 2026. Confirm the exact date and rubric with the course.

## Install and open the dashboard

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

## Demonstrate an existing run

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

## Show an early refusal

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

## Evidence to cite

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
