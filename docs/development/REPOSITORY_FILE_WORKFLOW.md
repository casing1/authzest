<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/REPOSITORY_FILE_WORKFLOW.md">한국어</a>
</p>

# External-project copy, verification and recovery

[Documentation index](../README.md) · [Proposal CLI](../guides/REPOSITORY_PROPOSALS.md) ·
[#202](https://github.com/casing1/authzest/issues/202) ·
[#152](https://github.com/casing1/authzest/issues/152)

## Status and delivery boundary

The current `repo-suggest` command captures explicitly selected external Python source, policy and
context and returns a proposed regression test, replacement source and host-derived diffs. It does
not create a copy, execute the project or correct the original checkout. The packaged owner-read GUI
and its fixed workers remain separate; they are not an external-project execution fallback.

S1 below remains an inert metadata contract. The separate
[S2 file-session API](../reference/REPOSITORY_FILE_SESSION.md) now implements live origin capture and
fresh private copy/diff/apply/restore decisions, checked using owned inert temporary files and fake
clocks/failures. No CLI/GUI operator, saved-workspace opener, target execution or original write is
enabled. The [S3 interface/case contracts](../reference/REPOSITORY_VERIFICATION.md) implement pure
declarations and supplied comparisons; the actual runtime sections below remain proposed. Design/source review does not approve
concrete case expectations, runtime images, source sharing or execution.
Stable publication remains held for actual external-project completion under #150–152/#189.

## S1: inert copy-plan contract

`authzest.codex.repository_copy_plan` exposes `RepositoryCopyPlan`,
`prepare_repository_copy_plan(request, response)` and
`validate_repository_copy_plan(plan, request, response)`. Preparation validates the complete current
request and response. Valid `no-change`, `unknown` and `refused` responses return `None`.
For `proposed-change`, it records:

- Canonical identities of the complete request and response, including model and explanatory fields.
- Role, exact relative destination, selected origin path if any, UTF-8 byte count and SHA-256 for each
  material file; exact before/after/restore source hashes and host-derived diff hashes.
- Layout version `1.0`, at most 128 KiB of material and a separate at-most-64-KiB host journal.
- Original generated-test path **uninspected**, fresh root and origin checks still required, and all
  effects/decisions unperformed. The plan contains no source text, diff, absolute root or approval.

Validation reconstructs the entire plan from the supplied current request/response and compares it
exactly. Rehashing edited metadata cannot satisfy that comparison. Constructing an object or importing
saved JSON grants no workspace, permission, authenticated provider provenance or runtime evidence.
S1 does no filesystem, network or process access. Its original-file effect describes this API, not
the earlier input capture or changes by another process.

## Proposed private layout and freshness

A later live session would create a fresh private directory, mode `0700`, with exclusively created
regular `0600` files and no symlinks/hardlinks:

```text
authzest-repository-<nonce>/
  project/<selected source and Python context paths>
  project/tests/test_authzest_regression.py
  evidence/policy.txt
  evidence/source.before
  evidence/source.after
  evidence/test.txt
  record.json
```

This is a **selected-source workspace**, not a recursive clone. Policy and recovery snapshots stay
outside the app tree. No unselected `.env`, credentials, dependency/configuration files, `conftest.py`
or unrelated tests are discovered or copied, and no synthetic `__init__.py` is added. A needed package initializer must be an
explicitly selected context and consume the existing selection budget. Missing imports are unsupported.
Empty selected Python files are allowed; proposed source and test must be nonblank. All bytes are UTF-8.

Reject equality and file/directory-prefix collisions before creating anything, including a selected
`tests/test_authzest_regression.py/child.py`. Also reject canonical caseless aliases (`NFD → casefold → NFD`) conservatively for
normalization/case-insensitive filesystems while preserving exact spelling. The original project's
generated-test path has never been inspected: a `/dev/null` test diff asserts only a new private
artifact. Exclusive destination creation must establish absence in the fresh copy; it cannot establish
absence in the original project.

The future live-origin capture must retain root/selected-file identities (or held descriptors) from
the initial local workflow review alongside its captured bytes, then compare them immediately before
copy. The existing content-only loader closes descriptors; a saved request, plan or `RepositoryInput`
cannot reconstruct this identity baseline or establish continuity since an earlier capture.
Before copying, recapture all selected original inputs with the no-follow bounded loader,
compare exact bytes and the current local root/file identities, and refuse changed inputs. Bind the
new private root, files and immutable evidence to a live current-process handle. Neither a content
hash nor the old `RepositoryInput.root` alone provides that live binding. No hostile-writer atomic
snapshot guarantee is claimed. If startup/copy partially fails, preserve the observed files and record
the failure; do not adopt them later by opening saved JSON.

After copying, operations check private identities and frozen bytes. Edits to the **original** must
not prevent recovery of the independent private copy. Edits to private source, test, snapshots or
journal block writes rather than being overwritten. The live handle retains the last self-committed
journal bytes/identity/state and advances them only after durable readback. Saved JSON never restores
that authority; an uncertain journal failure reports recovery-required, without automatic restore.
Original-project application has its own later
freshness gate below.

## Current decisions and recoverable writes

Proposed progression: runtime/case review → sharing → copy → before → exact diff acceptance →
private apply → after → private restore. Each mutation/execution has a complete current preview,
distinct live-session token, single-use decision and original monotonic expiry of at most 300 seconds.
Reject stale tokens, replay, imported decisions, automatic approval, deadline extension and reopen/resume
from saved records. Content identities identify artifacts; they are not decisions.

Before a write: revalidate identities and exact expected bytes; durably record intent; check the live
decision/expiry again immediately before commit; use exclusive temporary files and atomic replacement;
read back the destination; then record completion. Scope is the current single source only. Retain
the exact generated test and evidence. Refuse unsupported durability/metadata semantics. A failed
commit/readback/journal step preserves actual known state, poisons further ordinary mutations and
reports `recovery-required` when needed; never claim rollback just because a rename was attempted.

Restore separately checks that current private source equals the accepted after bytes and that the
before snapshot equals the captured before bytes, then replaces only that source with before.
It does not erase user edits, test artifacts, evidence or historical after
results. Final output distinguishes current source bytes from a historical passing after observation.
Runtime failure and file state are separate: a failed after check may permit separately reviewed
restore only when identities and actual bytes are known. Unknown state never becomes success.

## Proposed external runtime interface

External Python is untrusted. Keep the fixed owned workers and existing registries unchanged; create
a separate versioned runtime contract instead of accepting arbitrary paths in a packaged worker.
Do not import, collect or install target code on the host.

The first runtime supports self-contained, in-memory FastAPI apps with explicitly selected imports,
GET routes and bounded JSON responses. Review an `entry_source` from the selected Python files,
an import root of `.` or `src`, and a plain app-attribute identifier (default `app`); derive the module
path, reject factories and do not discover entrypoints. Lifespan is disabled. Database/services,
project dependency installation, external identity providers and real credentials are unsupported.
An unavailable import, fixture or setup requirement stops as unsupported, without a synthetic fallback.

The current proposal schema `1.0` makes no runnable-fixture promise. The separate pure `1.1` request
contract now defines a model-visible `test_interface`: explicit
entry source/import root/app attribute, trusted `client` fixture and lifespan disabled. Bind it to the
full prompt/request identity and keep independent case expectations private to the host. Preserve
the current `1.0` proposal-only default; do not turn saved `1.0` results into write/run authority.
AST-valid generated Python alone is not evidence of safe or runnable code.

For each phase, stage the exact current private bytes into separately sealed, verified inputs; do not
mount the live workspace. Use **three separate guests**, following the existing T/A/B separation:

| Guest | Inputs and purpose                                                                             | Authority                                                           |
| ----- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| T     | Generated test and selected source; trusted bootstrap supplies `client` without auth overrides | Pytest output and exit status are untrusted auxiliary observations  |
| A     | Selected source only; trusted launcher starts the explicit app with Uvicorn                    | Target responses are untrusted                                      |
| B     | Trusted fixed HTTP observer, request schedule; no source/test or expected answers              | Host validates bounded captured responses and compares expectations |

T and A have no network. B joins only A's network namespace, not its PID/mount namespace, and exposes
no host port. Each has a read-only root, dropped capabilities, no-new-privileges, no Docker socket,
host environment or credentials, and bounded temporary storage. T uses an isolated generated-test
path with explicit collection, disabled plugin autoload/config/conftest discovery and a trusted import
bootstrap. Target imports remain untrusted even with these measures. T cannot provide authoritative
independent-control records. B never imports target code; the host retains expected answers.

Proposed phase limits are one shared 40-second startup/request/completion deadline plus 10 seconds
for cleanup, not a reset for each guest/request. Each guest has at most 1 CPU, 512 MiB memory,
64 PIDs and 32 MiB tmpfs; aggregate captured output is at most 256 KiB. Enforce and record exact
image/launcher/codec/staged-byte identities, response bounds, exit status and cleanup of all guests.
No automatic retry or resumed phase. Host filesystem/Engine calls are not a hard whole-operation
wall-clock guarantee; these controls are not escape-proof isolation. Concrete images still need review.

## Independent cases and honest before/after gates

Maintain 4–8 human-reviewed cases, at most one GET each and one designated regression. Record
authorship, policy assumptions, role setup and expected **before and after** observations separately
from model output. Cover authenticated normal use, non-owner denial and anonymous denial where
applicable, plus explicit public intent or a reviewed not-applicable reason. AST declarations cannot
establish those policy intentions. A review string or case JSON is not authenticated human approval.

Initial requests use relative paths and bounded synthetic allowlisted headers, excluding Host,
Authorization, Cookie, proxy/framing headers and real credentials. No redirects, retries, absolute URLs,
callback/regex matchers or arbitrary request scripts. Define exact status and typed JSON/empty-body
expectations with strict duplicate-key/nonfinite-number rejection, HTTP framing/fragment limits and
bounded response bytes. The observer receives request schedules only; expected values remain host-side.

Before acceptance requires the exact reviewed before observations, a meaningful designated mismatch
against desired policy and a corresponding generated assertion failure. Collection/setup failure,
zero tests, skip/xfail, HTTP 500, timeout or malformed output do not reproduce the authorization defect.
The T failure is only auxiliary: independent host comparison must establish the reviewed observation.
After acceptance requires the generated regression to pass and all intended independent controls to
match, with every guest cleaned up. A target/test can game its own behavior; finite observations
support these reviewed cases, not general authorization assurance or arbitrary repository correctness.

## Original-project correction remains a completion gate

A successful private-copy after phase is not a corrected original repository. The product goal includes
an explicit final user decision to apply a verified source change to the original project. Keep that
work visible under #152 and #150; do not close them based only on private-copy recovery.

Before enabling original application, separately review its concrete design: recheck the original
root and **all selected** bytes/identities; bind the passing copy and exact diff; preview the current
single-file original write; preserve original metadata, backup and durable intent; refuse concurrent
edits; and implement explicit original restore/recovery without overwriting later user changes. New
test placement in the original needs a separately inspected absence/conflict decision. The S1 plan
does not inspect that path or authorize either write. Private recovery stays available independently
of original drift. No original-write API is implemented in this slice.

## Incremental delivery

1. **S1:** inert metadata plans, pure tamper/path/budget tests and paired design, delivered in #203.
2. **S2, current file API:** fresh private workspace and exact apply/restore with owned inert temporary
   files, fake clocks and failure peers; no runtime/operator boundary. Keep actual project operation
   and installed live acceptance pending; see #204 and the source API reference.
3. **S3:** pure versioned test interface, independent-case codec and supplied comparison are available
   under #206. Separate external runtime, raw HTTP observer and sealed staging still need fake
   process/Engine tests before reviewed images or actual external execution. Current v1.0 transport
   and file APIs do not accept the new v1.1 type.
4. **S4:** explicit CLI file workflow and installed, separately scoped real external before/after/
   recovery acceptance. Retain proposal-only defaults and complete readable/JSON results.
5. **S5:** reviewed original-project final application/recovery, with fresh original inputs and an
   explicit current user decision, before claiming that the product corrects external repositories.
6. **S6:** GUI over the shared engine, installed end-to-end evidence and current-candidate release
   review. Packaged demonstrations, static external scans and external live acceptance stay distinct.

Each slice must retain failures and unsupported outcomes, evidence limits, bilingual documentation
and exact-head CI/review delivery. A pure plan or fake-process result cannot satisfy a later live gate.
