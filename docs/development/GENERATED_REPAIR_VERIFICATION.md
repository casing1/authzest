<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_VERIFICATION.md">한국어</a>
</p>

# Generated repair verification — offline foundation

[Documentation index](../README.md) · [Generation contract](GENERATED_REPAIR_CONTRACT.md)

## Status and scope — 2026-11-09 KST

This is the first offline implementation slice of
[#152](https://github.com/casing1/authzest/issues/152), under
[#150](https://github.com/casing1/authzest/issues/150). The maintainer accepted the local Docker
design and the 17-case / 21-request maintained controls for **offline implementation**. This is
not permission to provision images, start containers or execute generated code.

The source API provides a content-bound verification preview, maintained control definitions,
data-only comparison and a disabled executor seam. It does not create a session or a copy, read
application files, write/apply/restore files, invoke Codex, start a worker or expose a new CLI option.
No runtime image, engine adapter or runnable container recipe is delivered. #152 remains open;
neither runtime reproduction nor a verified repair is established.

The original generation source, prompt and `pending-maintainer-review` policy metadata remain
unchanged. The separate control review label is `maintainer-accepted-offline-design`: it records
acceptance of this offline verification design, not a changed generation prompt, an independently
authenticated reviewer, an operational approval or a runtime observation. Product/report versions,
the existing registered-policy worker and registered file workflow are unchanged.

## Pure preview API

[The verification module](../../src/authzest/runner/generated_repair_verification.py) exposes:

- `build_generated_repair_verification_preview(request, proposal)` rebuilds the current fixed
  request/proposal and derives a detached verification preview.
- `validate_generated_repair_verification_preview(raw, request, proposal)` checks an untrusted
  serialized preview against those exact current inputs and the maintained definitions.

The immutable wrapper is `GeneratedRepairVerificationPreview`, its `kind` is
`generated-repair-verification-preview`, and `verification_preview_id` binds the complete payload.

The preview binds the complete inert proposal, host-derived application/test diffs and hashes,
maintained controls, and the fixed proposed isolation recipe and budgets. A digest mismatch,
changed expectation, altered budget or extra/missing field cannot silently change that plan.
Only a `proposed-change` can describe planned generated files; other proposal outcomes do not
become copy/execution requests.

`execution_boundary` is `unimplemented`; this is an offline-only preview. Copy/file absence is
planned, not filesystem-observed. Application, test materialization, execution and restoration
are not run; authorization assurance remains unknown. There are no effective image IDs, inspected
engine capabilities, current file snapshots, live decisions or accepted runtime receipts.
Hashes bind data, not provider authorship, caller authority, freshness or execution consent.

The executor seam is preparation-only: `GeneratedRepairVerificationExecutor.prepare(preview)`
returns `GeneratedRepairExecutorReadiness`; there is deliberately no `run` or `execute` method.
`DisabledGeneratedRepairExecutor.prepare` reports `not-ready` / `runtime-not-implemented`.
`prepare_generated_repair_executor(preview, executor=None)` revalidates the entire preview and
rejects readiness claiming that a runtime was invoked, effects occurred or execution is ready.
Caller-injected readiness implementations are trusted test seams, not a sandbox or capability.
Production code does not select or call a live runtime adapter. Passing a preview to this interface
is not approval and cannot start Docker.

## Maintained controls

[The controls module](../../src/authzest/runner/generated_repair_controls.py) owns the fixed
definitions, their validation and the data-only comparator. Expected values are maintained host
data, not generated assertions or values supplied by an app, relay or model response.

`build_generated_repair_controls()` returns `GeneratedRepairControls`;
`validate_generated_repair_controls(raw)` accepts only the complete current definition.
`compare_generated_repair_observations(raw, controls, candidate="before" | "after")` requires an
explicit candidate and the complete ordered fact set. Fact JSON has schema `1.0`, kind
`generated-repair-http-facts`, the exact `controls_id`, candidate and facts; each fact contains only
`request_id`, integer `status_code`, header pairs and canonical `body_base64`. This is a bounded
data format, not a public launcher or an import/resume option for a live session.

| Group                | Cases / requests | Expected repaired behavior                                                                                                      |
| -------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Owners               | 2 / 2            | `alice` / `doc-alice` and `bob` / `doc-bob`: 200 with exact original id, owner and body                                         |
| Cross-owner          | 2 / 2            | Both directions: 403, exact JSON `{"detail":"Forbidden"}`, no known protected plaintext marker in bounded response headers/body |
| No actor             | 3 / 3            | Both existing document IDs and the fixed missing ID: 401, exact JSON `{"detail":"Unknown demo actor"}`                          |
| Empty actor          | 3 / 3            | The same three document IDs: 401 with the same exact error body                                                                 |
| Unknown actor        | 3 / 3            | Fixed `mallory` actor and the same three document IDs: 401 with the same exact error body                                       |
| Missing document     | 2 / 2            | Each valid actor requesting the fixed missing document: 404, exact JSON `{"detail":"Document not found"}`                       |
| Normal-use sequences | 2 / 6            | Each actor's own read → other owner's document → own re-read: 200 / 403 / 200 with exact original successful payload            |
| Total                | 17 / 21          | Planned definitions, not observed case or HTTP counts                                                                           |

The before profile is different from the desired repaired profile: owners, invalid actors and
missing-document behavior stay intact, while each cross-owner request exposes the exact known
synthetic document. An import failure, timeout, unrelated assertion failure or a generic failing
test does not reproduce that omission. The after profile requires all maintained controls,
including both normal-use sequences; accepting only a selected subset is not repair verification.

The plaintext disclosure check has a finite known-marker vocabulary. It does not detect every
encoding, covert channel, transformed disclosure or behavior outside these requests. The
caller-controlled `X-Demo-Actor` is fixture data, not authentication or a trusted identity.

### Data comparison is not runtime evidence

The comparator consumes supplied bounded response facts and compares them with maintained
expectations. It performs no HTTP request and imports or executes neither generated source nor
tests. Missing, duplicate, reordered, malformed or unsupported facts must not be counted as
complete matching observations. A match says only that **supplied data matches a profile**.
It cannot establish where those facts came from, that an application ran, which file bytes ran,
whether isolation/cleanup succeeded, or that a generated repair is correct.

Comparison results use `status: "data-only"` and `comparison_status` of
`matches-expected-profile` or `profile-mismatch`, retain `provenance: "caller-supplied-unverified"`,
and explicitly set `execution_status: "not-established"` and `verified_fix: false`. Count fields
describe supplied data comparisons, not independently observed successful requests.

A future active workflow must independently obtain complete facts through the reviewed relay
boundary, bind actual captured file and runtime identities, and retain capture/cleanup evidence.
The generated pytest report remains untrusted auxiliary information: generated Python can forge
its own failure/pass report. It cannot replace host-compared maintained controls.

## Proposed isolation boundary — not implemented

The accepted direction is an optional trusted local Linux Docker engine, not host execution of
generated pytest and not a widening of the registered-policy worker. Each before/after phase
would use fresh roles:

- **T — generated test:** exact captured app/test bytes in a fixed pytest entry point, network none.
- **A — application:** exact captured app bytes, no generated test, fixed image-owned ASGI server,
  network none and a fixed container-local loopback port.
- **B — maintained relay:** separate PID/filesystem namespaces, no source/test mount; joins only
  A's exact network namespace, sends fixed requests and returns bounded response facts.
- **Host oracle:** keeps expected values and final verdicts outside generated Python and guests.

T runs separately from A/B so generated test state cannot carry into the maintained control run.
The proposed guest recipe requires fixed non-root identities, read-only roots, dropped capabilities,
no-new-privileges, seccomp and enforced CPU/memory/PID/tmpfs limits. Only exact read-only staged
input files may be mounted. There is no original-checkout, HOME, credential, result-journal or
Docker-socket mount, inherited host environment, host port, bridge/external network or model-chosen
command/dependency. No implicit image pull, build or dependency installation is allowed during a
check. These are proposed requirements, not capabilities this source slice has inspected/enforced.

The trusted OS, engine, reviewed images/dependencies and operator remain part of the boundary.
Containers are not escape-proof and do not protect against a compromised engine/kernel or every
hostile concurrent same-user writer. The local engine and image feasibility remain unverified.
Scan/offline preview do not require Docker; no unsafe host-execution fallback is planned.

### Future budgets

The preview binds these proposed ceilings. No timer, resource controller or live decision is
implemented by the preview/comparator itself.

| Resource                 | Proposed ceiling                                                                                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Per-stage local decision | Original maximum 300 seconds; single use, no refresh/replay/resume                                                                                   |
| Each before/after phase  | One shared 40-second setup/capture deadline for T then A/B; cumulative readiness at most 10 seconds within it; additional cleanup at most 10 seconds |
| T or A                   | 1 CPU, 512 MiB memory, swap limit equal to memory, 64 PIDs, 32 MiB tmpfs                                                                             |
| B                        | 0.5 CPU, 128 MiB memory, swap limit equal to memory, 32 PIDs, 8 MiB tmpfs                                                                            |
| Shared memory            | At most 8 MiB per guest                                                                                                                              |
| HTTP facts               | 512-byte status line, 32 headers / 4 KiB header block, 8 KiB body per response                                                                       |
| Process output           | 256 KiB combined stdout/stderr across all phase roles, bounded during capture                                                                        |
| Retained session data    | 2 MiB total record/artifact budget                                                                                                                   |

The existing 16,384-byte per-source/test and parse-only AST budgets stay unchanged. Phase time
does not restart at a new role/request; readiness is not an extra execution allowance. Timeout,
OOM, truncation, malformed data, incomplete capture, persistence failure and unconfirmed cleanup
must remain distinct failures. Filesystem/daemon/kernel operations have no universal wall-clock
guarantee. Future active acceptance must measure effective enforcement, not trust flags alone.

## Future copy and recovery semantics

No copy or source/test write happens in this slice. The intended sequence is:
copy → before check → source-diff acceptance → source apply → after check → restore, each with
its own current, content/file/prior-result-bound decision and failure state.

Future copy creation must explicitly authorize both the fixed before `app.py` and materialization
of `tests/test_generated_ownership.py` into a fresh private copy. The planned absent test must be
observed absent before exclusive creation and readback. This creates the test **before** its PoC
run and does not apply the after-app source. Later source application consumes only the exact app
replacement diff; it is not an atomic app-plus-test patch.

The copy-created restoration target is the exact before-app bytes **with the generated test
retained unchanged**, along with evidence. Restore does not recreate an absent-test original tree
or delete artifacts. The original checkout is never a write target or runtime mount. Future file
operations must refuse symlinks, hardlinks, identity replacement, stale/missing/user-edited files
and uncertain state rather than overwriting them. Single-file atomic rename is not a same-user
compare-and-swap guarantee; partial initialization and fsync/journal failures cannot claim no writes.

Cleanup must identify exact session-owned guests, confirm termination/removal and preserve bounded
evidence. Unknown cleanup, changed files or uncertain replacement requires inspection/recovery-required,
not forced restoration. Restoring bytes cannot turn a failed repair check into success.

## Next implementation slices and gates

1. Add a dedicated private-copy/session state contract with temporary-file refusal, exact-diff,
   test-materialization and restoration regressions. Do not relax existing registered worker APIs.
2. Add a mocked engine/capture lifecycle and strict relay-fact boundary. Cover ambiguous create/start,
   forged reports, reordered/oversized facts, cancellation, persistence and cleanup failures.
3. Add explicit CLI plans, individual decisions, escaped readable states and versioned result
   records only after those seams are reviewed; the current commands remain unchanged.
4. Separately review image provisioning/capability checks and installed-candidate runtime validation.
   Real AI sharing, generated execution, copy/application/recovery and public run disclosure require
   their applicable scope; offline tests/acceptance labels grant none of that authority.

Offline regressions use inert source text, supplied facts and disabled/fake boundaries only; they
must not import, compile, collect or execute generated app/tests. A later accepted run must bind the
exact installed candidate, source/test/diff, controls/review, inspected engine/images and actual
before/after/restored files, with complete capture and confirmed cleanup. No current preview or
comparison satisfies those gates. Read-only local UI work (#153), delivery (#85), risk review and
release remain separate; no issue is completed by this foundation.
