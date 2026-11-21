# Course demonstration and evidence

[한국어](../i18n/ko/guides/COURSE_DEMO.md) · [Documentation](../README.md) · [Course delivery #85](https://github.com/casing1/authzest/issues/85)

Use the `0.1.0` source candidate at [`50706ff`](https://github.com/casing1/authzest/commit/50706ff28f0043497a04b411760e3b41b385b883). The live demonstration shows how one FastAPI router becomes two route registrations and how the dashboard reports a workflow that stopped before execution. The AI-assisted repair example uses a separately dated observation.

## Before the presentation

On macOS or Linux, use Python 3.12 and Node.js 22.13 or later in the 22.x line, or Node.js 24. Install once before presenting. The dashboard needs the editable source installation and the built frontend. These steps were checked on macOS arm64 with Python 3.12.7 and Node.js 24.11.0.

```bash
git clone https://github.com/casing1/authzest.git authzest-course
cd authzest-course
git switch --detach 50706ff28f0043497a04b411760e3b41b385b883
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci --ignore-scripts
npm --prefix frontend run build
.venv/bin/authzest --version
```

Check for `authzest 0.1.0`. Run the remaining commands from the same checkout.

## 1. Show how route registration works

```bash
.venv/bin/authzest scan examples/fastapi_inventory
.venv/bin/authzest scan examples/fastapi_inventory --json
```

Point out `GET /health`, `GET /v1/catalog/items` and `GET /v2/catalog/items`. The catalog entries point to the same function in `app/routers/catalog.py`. The two `include_router` declarations in `app/main.py` supply different prefixes. AuthZest reads those declarations without importing the example. The JSON report uses schema `1.2` and reports `python_files: 4`, `route_count: 3`, `analysis_status: bounded` and `codex_status: disabled`. A route declaration alone does not establish who can access a deployed endpoint.

## 2. Prepare a workflow result to display

This example deliberately omits the required runtime profile. The CLI exits with code `2` before model sharing or execution. Save the printed file path for the browser file chooser.

```bash
(
  umask 077
  demo_dir=$(mktemp -d) || exit 1
  status_code=0
  .venv/bin/authzest codex-generate --model course-demo --file-workflow --json > "$demo_dir/refused.json" || status_code=$?
  if [ "$status_code" -ne 2 ]; then
    printf 'Expected exit 2, received %s\n' "$status_code" >&2
    exit 1
  fi
  printf '%s\n' "$demo_dir/refused.json"
)
```

The workflow JSON uses schema `1.0`. It records `invalid-input`, `application_turn_attempts: 0` and `not-run` for both execution and patch application.

## 3. Present the local dashboard

```bash
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

Open [the local dashboard](http://127.0.0.1:8000) and leave the terminal running.

1. Select **Static inventory → Analyze repository**. Show the same three routes as in the CLI.
2. Select **Workflow results**, choose `refused.json` and select **Open result**. Point out the recorded refusal and the empty before/after observations. The import accepts workflow-result JSON up to 512 KiB. The static scan has its own tab.
3. Switch the language to **한국어**. The labels change and recorded status values stay readable. An imported record has provenance `imported-unverified`. Opening the file displays its claims without starting a new run.

Press Ctrl-C in the terminal when finished. [Result viewer guide](RESULT_VIEWER.md)

## Evidence to cite

| Topic                         | Evidence for the presentation                                                                                                                                                                                                                                                                                                                                                                                                          |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Candidate installation and UI | Fresh CLI installation and upgrade from the public alpha.4 tag source each passed 13 checks. The source dashboard displayed the schema 1.0 refusal and static inventory. [Candidate PR #180](https://github.com/casing1/authzest/pull/180)                                                                                                                                                                                             |
| Earlier AI-assisted repair    | One installed run at `34baebc` recorded a model-proposed test and repair. Independent checks matched their expected outcomes in both phases, and the private copy was restored. Cite this as historical evidence. The candidate's new end-to-end success record remains open. [Historical observations](https://github.com/casing1/authzest/blob/c45462889fcbfa5b8354558336f6d4bd1540c27d/docs/guides/COURSE_DEMO.md#evidence-to-cite) |
| Native packaging              | Linux x64, macOS arm64 and Windows x64 passed 52 static scan and offline preview checks each. The downloadable Actions artifacts were built for candidate testing. [Checksums and workflow](https://github.com/casing1/authzest/issues/150#issuecomment-7000856136)                                                                                                                                                                    |
| Evaluation and release        | Independent evidence comparing AI performance remains unavailable under #84. The developer-tool disposition is recorded for `50706ff`. The public release at the time of this walkthrough was alpha.4. [Evaluation #84](https://github.com/casing1/authzest/issues/84) · [Release checklist #150](https://github.com/casing1/authzest/issues/150)                                                                                      |

If you have permission to display the earlier workflow record, open it locally to show its recorded proposal, diff and recovery. Older unversioned records carry the `legacy-unversioned` label and lack original source evidence. The public historical summary can be used on its own. Keep private records and local paths off shared slides.
