<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/RUNTIME_VERIFICATION.md">한국어</a>
</p>

# Owned-fixture runtime verification

[Documentation index](../README.md) · [Codex fixture](CODEX_FIXTURE.md) · [Copy application](FIXTURE_APPLICATION.md)

## Scope

[#54](https://github.com/casing1/authzest/issues/54) adds an opt-in runtime check to the maintained
configuration demonstration. It is available in published
[alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) POSIX binaries and source,
not the earlier alpha.2 binaries. The ordinary
`scan` remains offline and source-only. The existing source-configuration verification stays the
default; `--runtime-check` selects a different plan, not permission to execute it.

Only the two exact bundled `main.py` variants are accepted. After byte-for-byte comparison, the worker
executes the corresponding bundled constant, never a caller-selected path, arbitrary input program,
model-generated test or command. The only supported change is `debug=True` → `debug=False`.
The worker observes the instantiated application's `debug` boolean and performs one in-process
ASGI `GET /health`, expecting HTTP 200 and JSON `{"status":"ok"}`. It runs no exploit reproduction.

This is a benign configuration and health smoke, **not authorization correctness, a reproduced
vulnerability or a verified security fix**. It does not test authentication, object ownership,
lifespan hooks, a real HTTP server, other routes, or general FastAPI compatibility.

## Run

For a source installation, use a trusted Python 3.12 environment and install the optional dependency explicitly:

```bash
python -m pip install -e '.[fixture]'
```

Alternatively, use a checksum-verified alpha.3 POSIX binary following the
[release instructions](../releases/RELEASING.md#verify-and-recover); it bundles Python and the fixture
dependencies, so that install step is unnecessary. Neither distribution bundles Codex or credentials.
With either installation, run the command below; replace `authzest` with the exact downloaded path if
the executable is not on PATH:

```bash
authzest codex-fixture --model MODEL --timeout-seconds 120 --runtime-check
```

`MODEL` is an explicitly selected account-accessible model, not a fallback. The Codex path requires
the version and managed ChatGPT login described in the [Codex guide](CODEX_FIXTURE.md). Source sharing
can consume subscription usage; runtime checking itself makes no model call. AuthZest never installs
dependencies during validation. Missing runtime dependencies produce `not-run` with
`runtime-dependency-unavailable`, treated as unsuccessful verification by the workflow.

For a development-checkout demo with a caller-authored mock draft and **zero provider calls**:

```bash
python -m scripts.demo_verify --runtime-check
```

Omit `--runtime-check` to keep the existing source-only configuration checker. A session selects one
check; it does not silently run both. Application and runtime checking require supported POSIX
operations; Windows fails closed for this workflow while existing Windows `scan` support is unchanged.

## Separate decisions and retained evidence

The live command requires `share <request_id>`, then `apply <proposal_id>`. After applying only to a
fresh private copy, it displays a runtime plan containing the exact source, file identity, proposal,
worker source/digest, expected checks, and bounds. Only `verify <plan_id>` approves that plan. Enter
declines; `cancel` cancels. Neither the selector, login nor application approval grants runtime permission.

The latest decision is in-memory, expires within 300 seconds and is consumed at most once. Plan/source
changes, expired decisions, unavailable journals and conflicting filesystem state refuse execution.
The source is rechecked after the intent record and after the worker. A failed check does not
automatically restore anything: the separate `restore <proposal_id>` choice remains available when
safe, and detected later edits are not overwritten. Inspect retained copy/snapshots/`record.json`.

Runtime records use journal schema `1.2` (not the separate scan report schema). They identify
`verification_scope: owned-fixture-runtime`, `verification_status`, `runtime_verification_status`,
the checked source/check/worker digests, elapsed time, process exit, and runtime observations.
Observed Python/FastAPI/Starlette/Pydantic versions are metadata, not attestation of trusted binaries.
Static-only sessions retain journal schema `1.1` and runtime status `not-run`.

A successful AFTER check is `passed` / `runtime-check-passed`; the BEFORE variant is
`failed` / `debug-enabled` even when its health route responds normally. Missing, refused or expired
checks are `not-run`. Timeout, malformed worker output, a later edit or uncertain result recording
cannot become `passed`. An outer interruption can omit unknown status; inspect the retained record
instead of assuming that no execution occurred. A result remains historical evidence of its checked
AFTER digest even after an approved restoration to BEFORE.

## Process boundary and limitations

The fixed worker gets bounded source bytes over stdin, a private working directory, a reduced
environment, at most 1,024 input bytes and 4,096 output bytes, a five-second startup/I/O deadline,
and a separate one-second process-group kill/reap allowance. There is one attempt, no retry and no
shell. Raw worker stderr and exception details are not exposed as diagnostic evidence.

ASGI messages stay in memory: no TCP/UDP listener or HTTP client is used. Internal event-loop IPC
and framework threads may still be created. This is **not an OS/network sandbox**. Python source mode
uses `-I` but not `-S`, so trusted interpreter site startup hooks and installed dependencies may run.
Frozen mode uses bundled dependencies and preserves only validated existing PyInstaller parent
context for the same-executable child; this is consistency checking, not executable attestation.
Do not use an untrusted interpreter, executable or dependency environment.

The approval record is not authenticated human identity, a restart/resume receipt, or hostile
concurrent-writer protection. No arbitrary source, generalized runner, generated tests, automatic
installation, network scanning or exploit workflow is supported.

## Packaging gate

Release builds and fresh downloaded-artifact jobs run a distinct fixed runtime smoke in addition to
the existing scan smoke. The internal `_runtime-smoke` diagnostic accepts no target path or command:
it asks the actual packaged parent to launch its same-executable worker for the bundled AFTER sample.
It is a packaging diagnostic, not a user decision receipt or a replacement for end-to-end consent tests.

The matching-platform external smoke deadline remains 45 seconds; the worker retains its own
five-second plus one-second bounds. POSIX requires the exact successful runtime evidence; Windows
requires an explicit unsupported result without launching a worker. No live Codex account is used.
Passing this gate does not establish clean consumer installation, upgrades, signing/notarization,
live-model integration or authorization security. A release is published only after the separate
[release procedure](../releases/RELEASING.md) succeeds.

The request/response probe follows the official [ASGI HTTP specification](https://asgi.readthedocs.io/en/latest/specs/www.html).

## Bounded live acceptance — 2026-09-12

On runtime commit `ce2834c354f7c25d53e417382f41687296a508fc`, one newly approved live source-CLI
attempt completed with exit 0: Codex draft → exact-diff copy application → separately approved
runtime check → separately approved restoration. Original main/worktree fixture hashes and the
restored copy all remained `c10770594e77cd1c1ec93c19ef2b810aea34ed873d8dbf392b57e50a1c2729df`.
The checked AFTER hash was `e010818e7259ad5c1ebfc5dfcb6dc046100376c778a70d0657d7ebb1ed7fdcfe`.

- Existing Codex-managed ChatGPT login, Codex 0.153.0, negotiated model `gpt-6-astra`, one application
  attempt, 120-second deadline, no application retry/fallback. Provider-reported usage: 5,573 input /
  376 output tokens; draft latency 15,309.473 ms; observed warning/retry notices 1/0.
- Runtime: `passed` / `runtime-check-passed`, 287.004 ms, exit 0, `debug: false`, health 200 and
  `{"status":"ok"}`. Observed Python 3.12.7, FastAPI 0.141.1, Starlette 1.6.0, Pydantic 2.13.5.
- Plan `verification-1e279e9af021e553552ec084c81a529f3e808abb52a91226bc0fe5741f95eb2f`;
  worker `05ef28b904eadf28ffe149e0b0d045e3b2d58086edfe0a7139c417265719f2a7`.
  Retained journal schema 1.2 records the consumed verification decision and restored state.

The assistant reviewed and entered the exact phrases under the user's bounded approval; this is
not independent human-review attestation. The approval is exhausted. Reported tokens and zero
observed recovery notices do not establish a hard billing/provider-attempt cap or served-model
attestation. This single benign fixture is not general repository, authorization or security-fix
acceptance. Local tests and native fake-transport evidence remain distinct from this real call.

The same runtime commit passed **1,548 Python tests** in 168.73 seconds, Ruff, frontend lint/format/build,
and the bilingual documentation audit. The first restricted run's five existing descendant-cleanup
checks could not run `ps`; the unchanged tests passed with local process-inspection permission.

The macOS ARM64 development binary SHA-256 was
`0b6ef1b4ddf541a74a0b18b2fde61b1867c9f03bc5d1274af27a59e6d96a5183`.
Selected/relocated scan smoke passed 14/14 and fixed runtime smoke passed 2/2. A separate native
production CLI → local fake Codex → same-native runtime worker → restore walkthrough passed with
four exact choices, 15.593-second outer startup and 1,708.617-ms worker time. That native walkthrough
used zero real provider calls; fake model/usage values are scripted test data. It preserved the
original hashes and recorded journal 1.2 with the historical passed AFTER digest after restoration.
PyInstaller's local semaphore required execution outside the restrictive tool sandbox; no deadline
or success condition was weakened. Three-platform release/download verification remains a separate gate.

## Published alpha.3 artifact acceptance — 2026-09-12

[Alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) was published at
2026-09-12T09:00:49Z from `99be6f5614d283befa2a421b64f84958b680f92f`, with package `0.1.0a3`.
Three-platform builds and fresh matching-platform artifact jobs passed. All six public files were
downloaded, their three SHA-256 manifests checked, and every file matched to the checked tag artifacts.
The public macOS binary SHA-256 is
`8c75e299e9699c0a08dc30924478013c05f918d33e35bc874178dbe027a782c6`, distinct from the development build above.

The public macOS executable passed seven relocated scan checks and one fixed runtime check through
standard-library controllers under Python `-I -S`, without importing project dependencies. This does
not assert that those dependencies were absent from the controller's environment. Linux/Windows execution evidence comes
from matching-platform CI and identical public bytes, not local macOS execution. Windows checked an
explicit unsupported/not-run outcome without a worker, not runtime feature support. The external
45-second and worker five-second plus one-second cleanup bounds were unchanged; local macOS IPC
needed permission outside the restrictive tool sandbox. These package checks made no model/auth calls
and do not establish live-model package acceptance, clean-device installation/upgrades, signing,
general repository support or security-fix efficacy. See the [release record](../releases/RELEASING.md)
for the exact workflow and public-download evidence; it does not alter the historical live/local results above.
