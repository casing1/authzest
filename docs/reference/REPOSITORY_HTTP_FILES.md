<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/REPOSITORY_HTTP_FILES.md">한국어</a>
</p>

# HTTP private files and current input checkpoints

[Documentation index](../README.md) · [Frozen scope](../development/0.1.0-SCOPE.md) ·
[HTTP cases](REPOSITORY_HTTP_VERIFICATION.md) · [HTTP image preparation](REPOSITORY_HTTP_IMAGES.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## Delivery and design boundary

These separate Python source APIs implement the frozen single-file HTTP layout, current-process
private decisions and A-only sealed inputs. They adapt maintained origin/file/guard algorithms while
leaving the old v1.0/v1.1, generated-test and T/A/B validators unchanged. They do not implement an
external CLI/GUI operator, contact Codex/an Engine, execute source, observe HTTP or change the original
project. `repo-suggest --http-poc` remains proposal-only.

The file session is trusted caller coordination. Its private apply step does not assert that a
before/after test ran or that a repair is correct. A later product operator must separately require
current direct phase results. Saved plans, records, snapshots and supplied comparisons cannot supply
that authority. Final original-file application and recovery remain separate required work.

## Exact source-only copy plan

`authzest.codex.repository_http_copy_plan` provides `RepositoryHttpCopyPlan`,
`prepare_repository_http_copy_plan(request, response, cases)` and
`validate_repository_http_copy_plan(plan, request, response, cases)`.

Preparation validates the entire schema 2.0 request/response and independent case/verification plan.
It binds their complete identities, exact source transitions and host-derived diff. A validated
no-change/unknown/refused response returns `None` and may omit cases. A proposed change must match
the designated independent PoC case. Metadata rehashing cannot replace reconstruction from current
inputs. The plan contains no live root, decision or material text and performs no I/O.

## Private state and exact decisions

`RepositoryHttpFileSession(origin, request, response, cases, copy_plan)` owns one unchanged
`RepositoryOrigin` only after all constructor validations succeed. It uses a separate schema 2.0
session/plan/decision identity and at most one newly allocated private tree:

```text
authzest-repository-http-<nonce>/
  project/<selected-flat-source.py>
  evidence/policy.txt
  evidence/source.before
  evidence/source.after
  record.json
```

The private file store accepts exactly these five ordinary files. No contexts, generated tests,
package initializers or other project files are copied. Directories are owned/private mode 0700 and
files 0600. Only the selected private source and journal are replaceable; original paths are never
write targets. Selected source/snapshots are bounded to 16 KiB each, policy to 8 KiB and the host
journal to 64 KiB. Case expectations remain host-held.

The separate prepare/decide/perform steps are copy → accept-diff → apply → restore. Each requires the
exact current live plan/decision object and current confirmation phrase, one use and at most 300
seconds. Repeating preparation does not extend its deadline. Source freshness is checked before
copy; private continuity, full contracts and expiry are rechecked before effects and final writes.
Plans and phrases do not authenticate a human, provider or policy review.

Held descriptor/name/byte checks refuse ordinary edits, same-byte inode swaps, aliases and changed
membership. Pending intent is journaled before source replacement; exact readback and the completed
journal bind the confirmed revision. Interrupted or uncertain writes retain files and the actual
commit/cleanup observations in a recovery-required result. There is no automatic retry, blind
rollback, saved-session opener or adoption of an existing tree. Closing releases descriptors and
retains artifacts. Synchronous filesystem calls are not a whole-filesystem time bound or atomic CAS
against hostile same-user writers; trusted callers must exclude concurrent writes.

## Current private-file checkpoint

The internal `_capture_runtime_checkpoint(phase)` issues `_RepositoryHttpRuntimeCheckpoint` only
for quiescent copied-before or applied-after state. It rereads actual private source, policy,
before/after evidence and the complete current journal, then binds the full request/response,
cases/verification/copy plan, phase, session/revision and root/file identities. An after checkpoint
therefore observes the applied private file; proposal `after_text` alone is insufficient.

The same issuer's `_recheck_runtime_checkpoint` accepts only its exact current object and repeats
current file checks. Pending decisions, later revisions, closure, process/thread changes, copied or
serialized objects and mismatched sessions do not qualify. A checkpoint is an internal current-file
binding, not permission to execute or a runtime result. Changes to the original after private copy
do not establish permission to overwrite it; final original application needs a fresh separate gate.

## A-only sealed input staging

`RepositoryHttpInputStage(session, request, response, cases, plan, phase)` validates the complete
HTTP/case/plan correspondence against that exact issuer checkpoint. It seals only:

```text
<private-stage>/
  input/manifest.json
  input/project/<selected-flat-source.py>
  record.json
```

Input files use 0444 and input directories 0555. The outer directory remains 0700; its 0600 host
record is outside inputs. No separate policy, oracle, journal, generated-test or ambient credential
files are copied. Selected source is preserved verbatim, including any literals it already contains.
There is no B stage: B receives the existing request-only schedule over bounded
stdin plus EOF, without source/policy/oracle mounts.

Allocation hooks, staged readback, snapshots and create-plan construction recheck private and staged
files before and after use, including when a builder raises. Stale revisions, edits, changed sealed
permissions, extra members, reentry and uncertain cleanup are refused with partial artifacts retained.
`prepare_create` returns `RepositoryHttpStagedCreatePlan` data with the current measured input
snapshot and fixed A create-plan declarations. It does not create or start a container.

## Remaining operator and acceptance

Reports retain execution not-run, authorization unknown and `verified_fix=false`. Offline owned-file
and fake-callback passes do not establish policy truth, safe images or actual repair verification.
The separate [runtime input/metadata checks](REPOSITORY_HTTP_RUNTIME.md) now prepare HTTP profile,
client and stopped-configuration comparisons. Concrete image/runtime acceptance and current direct
host phases must still connect to the CLI operator. Final original diff approval, backup, edit-conflict refusal/recovery,
installed actual acceptance and saved-result viewing remain open under #152/#150. No release follows
from these source APIs.
