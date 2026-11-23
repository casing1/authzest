# External repository runtime foundation

[Documentation](../README.md) · English · [한국어](../i18n/ko/reference/REPOSITORY_RUNTIME.md)

[#208](https://github.com/casing1/authzest/issues/208) implements selected-byte staging, separate
T/A/B guest entry sources, scheduled HTTP primitives and strict unexecuted runtime declarations.
It extends the [S3 contracts](REPOSITORY_VERIFICATION.md) and
[S2 private file session](REPOSITORY_FILE_SESSION.md) under the
[external file-workflow design](../development/REPOSITORY_FILE_WORKFLOW.md).
Owned temporary files and fake import, pytest, server, socket and kernel collaborators verify this
foundation. No external application/test, image build, guest or model was run to establish it.
There is no new CLI/GUI operator, original-project write, runtime acceptance or release.

## Current private checkpoint and sealed inputs

`RepositoryFileSession` retains its v1.0-only constructor and ordinary file decisions. Its internal
runtime checkpoint reads and verifies a quiescent current `copied-before` or `applied-after` copy,
including selected source/context bytes, generated test, evidence, journal revision and file identities.
Only the exact issued live checkpoint can be rechecked; pending decisions, transitions, edits,
replacement, a closed session or an old object prevent adoption. An unchanged checkpoint can serve
separate T and A stages. Saved JSON cannot reopen it or grant execution authority.

`RepositoryInputStage(session, request, response, cases, plan, phase, role)` requires that live S2
checkpoint, a current S3 v1.1 request/response, host-only cases and their complete verification plan.
It reconstructs the entire v1.1 request from the S2 base and compares the full response against the
existing v1.0 session response. This internal correspondence is not a saved-request downgrade,
new write API, provider-authorship proof or case approval.

Each T/A stage creates a fresh retained private tree:

```text
stage/                         # host-private; never mounted as a directory
  record.json                  # host-only checkpoint and stage evidence
  input/
    manifest.json
    project/<selected paths>   # source and explicitly selected Python context only
    tests/test_authzest_regression.py   # T only
```

Inputs become mode `0444`, input directories `0555`; the outer directory remains `0700` and record
`0600`. Checks cover descriptor/named identities, exact membership, modes, ownership, single-link
files and bytes before/after staging and create planning. Ordinary changes invalidate the stage;
these checks are not atomic protection against a hostile writer with the same host account.
Partial failures retain files and allocation/cleanup facts. `close()` closes held host descriptors,
without deleting evidence or claiming guest cleanup. Snapshots and stopped-create plans are historical
observations, not resumable sessions or permission to run.

## Shared manifest and per-file mounts

The standard-library-only `_repository_manifest.py` is both a packaged host helper and a separately
pinned guest asset. It validates canonical manifest bytes, the request/interface IDs, complete explicit
test interface and source/test descriptors. There are 1–5 selected Python files, at most 16 KiB each
and 64 KiB combined; a T test is nonempty and at most 16 KiB. The manifest is at most 16 KiB.
Nested packages retain the S3 initializer and module-alias rules. T includes test metadata; A has
`test: null`.

Stopped-create data declares individual read-only binds at `/input/manifest.json`,
`/input/project/<selected path>` and, for T, `/input/tests/test_authzest_regression.py`.
It does not mount the full private copy, policy, expected answers, journal, host record or unrelated
repository files. Before target import, guest source verifies the exact mount set and captured
file sizes/hashes. Hashes and the manifest ID bind data; they are not runtime provenance or consent.

## Separate guest bootstrap

The maintained sources live under `runtime/repository/`, separate from the unchanged fixed-case
launchers. Their entries require the exact Linux script, Python `-I -B` and UID/GID `65532`.
They clear inherited environment/configuration and remove input search paths. Kernel checks precede
project imports and require the declared read-only mounts, resource/cgroup settings, no capabilities,
no-new-privileges, seccomp, private process view and narrow network observations. These diagnostic
checks do not attest a reviewed image, escape-proof isolation or stress-tested limits.

Trusted pytest/TestClient or Uvicorn dependencies load before the explicit `.`/`src` project root
becomes importable. Cached-module and protected dependency-name conflicts are refused. Only the
declared module and plain app attribute are selected; no host target import, project setup,
installation, discovery, factory or import fallback is added.

- T collects one explicit generated test with no conftest, automatic plugins, project pytest config
  or cache. An explicit trusted `client` fixture constructs TestClient without entering its lifespan
  context and closes it afterward; no authentication overrides are installed. Output and exit status
  remain untrusted auxiliary data.
- A serves the explicit app through a trusted ASGI3 wrapper, preventing a zero-argument factory probe
  from entering the target. Uvicorn uses fixed loopback port `8765`, lifespan off, one worker and no
  reload, proxy-header processing or environment file. Its startup marker can be forged by target
  code and is only a hint.

## Request-only B observer

B has no input mounts or source/test access. A future host must attach before start, send the exact
bounded request-only schedule on stdin and close stdin. The guest accepts at most 16 KiB and receives
an original remaining-time snapshot of 1–40,000 ms. Its clock starts before guards and stdin reading;
waiting for EOF can still block, so the original host deadline and cleanup cannot be replaced by this
guest-local check.

The HTTP codec accepts 4–8 scheduled GETs to `127.0.0.1:8765`, without expected answers. It uses bounded
HTTP/1.1 Content-Length framing, typed JSON/empty bodies and explicit error records; redirects are not
followed and there is no reconnect/resend. It stops on the first failure while retaining all scheduled
rows. Stream closure is not T/A/B container cleanup. Captures are unverified data and cannot become a
successful live phase, reproduced defect or verified fix by being imported into S3.

## Unexecuted profile and image baseline

`validate_runtime_profile` requires maintained asset, lock and recipe pins; `build_container_create_plan`
returns only stopped-create argv/metadata with `planned-not-executed`, no execution authority and
`verified_fix: false`. The declarations budget each phase at 40 seconds plus 10 seconds for cleanup,
with finite output limits. T/A declare 512 MiB, one CPU and 64 processes; B declares 128 MiB, half a
CPU and 32 processes. T/A use network `none`; B names A's network namespace. Effective enforcement
and cleanup remain future host observations.

Create-plan paths currently use a narrow ASCII subset without spaces; kernel mountinfo decoding is
also ASCII-only. S3 may accept broader Unicode context paths, so S3 acceptance does not guarantee a
supported create plan or guest import. The bootstrap can represent escaped spaces in supplied mount
facts, but this does not expand the create-plan path subset. Missing dependencies/imports or unsupported
configuration must fail rather than install tools or broaden mounts.

The new recipes and asset manifest under `runtime/repository/images/` define a **new source baseline**.
They retain pinned base/lock inputs and separate entry assets; image IDs are absent and contents are
not verified. Prior fixed-case images or their earlier acceptance cannot satisfy these pins.
No image was built, inspected, accepted or run for this foundation.

A later host must verify fresh engine/config/image identity, persist owned guest names, inspect stopped
configuration, enforce the original deadline/output budget, obtain direct independent observations,
assemble a live phase and confirm exact guest cleanup. CLI/GUI integration, current sharing/execution
decisions, installed external-flow acceptance and separately reviewed original-project final correction
remain pending under #152/#150. Existing S3 supplied comparisons stay `supplied-unverified`; these
sources do not approve independent cases or unlock file application.
