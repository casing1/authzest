<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/DEVELOPMENT_PLAN.md">한국어</a>
</p>

# AuthZest Development Plan

[Documentation index](../README.md) · [Public roadmap](https://github.com/casing1/authzest/issues/1)

## Product direction

Build an installable, CLI-first FastAPI source-evidence tool for the OSS course. The course-release
deliverable is one maintained, owned access-control scenario: source evidence → newly generated
defensive PoC/regression test → AI-authored repair or valid no-change/unknown → exact-diff approve/decline
→ approved new-copy application → separately approved before/after checks → inspectable recovery.
Codex is a core goal, not an optional explanation add-on. Keep deterministic scan useful without an AI account.

Keep parser/analyzer, Codex adapter, runner and presentation boundaries independent. The existing
local API/React dashboard currently shows static inventory; presenting actual workflow results is now
a required release deliverable. Initially keep execution and approval in the CLI, with the local UI
reading results rather than adding a second execution/consent surface. Cloud deployment is unnecessary.
Model improvements do
not justify rewriting the product as an autonomous agent or general Python interpreter. Evidence-assisted
value is a hypothesis to measure, not an established advantage; see [model strategy](MODEL_STRATEGY.md).

## Course-release priorities — 2026-11-09 KST

[#150](https://github.com/casing1/authzest/issues/150) tracks the stable course release. This order
supersedes earlier benchmark-first, optional-UI and template-only completion targets; it does not alter
historical receipts. The accepted registered-template flow is a foundation, not completion of this target.

| Priority                                                          | Required delivery                                                                                                                                                                                                                                                                                                                                                                            |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 — [#151](https://github.com/casing1/authzest/issues/151)        | One maintained FastAPI object-ownership scenario with explicit policy and in-memory data; generate a new defensive test and an AI-authored patch to one application source file. Do not offer the registered after-template as a repair choice or relabel template selection as generation.                                                                                                  |
| 2 — [#152](https://github.com/casing1/authzest/issues/152)        | Design and implement separately approved, isolated before/after checks of the reviewed generated test and independent owner/non-owner/anonymous/normal-use controls appropriate to the scenario. Apply only the reviewed exact diff to a new copy, refuse stale or user-edited input, and retain refusal, failure and restore evidence. A model-authored test alone does not prove a repair. |
| 3 — [#153](https://github.com/casing1/authzest/issues/153)        | Use the local React UI to display actual scan, PoC/test, diff, before/after and recovery results, including failed/not-run/unknown states. Keep initial execution and approvals in the CLI; no cloud deployment is required.                                                                                                                                                                 |
| 4 — [#85](https://github.com/casing1/authzest/issues/85) and #150 | Complete the reproducible installed workflow/demo, honest minimum release evidence, and implementation-matched English README plus Korean/Japanese/Russian translations. Validate the exact release candidate and obtain a fresh [#89](https://github.com/casing1/authzest/issues/89) disposition before publication.                                                                        |

These are pending implementation and acceptance requirements, not authority to run generated code.
The new execution boundary, isolation, permitted operations, limits and failure handling must be designed
under #152 before any separately approved model/source sharing or active test/apply/restore operation.
Previous fixture approvals cannot authorize the new scenario. Arbitrary repositories, general code
execution and multi-file repair remain outside this first delivery.

Broader [#84](https://github.com/casing1/authzest/issues/84) benchmark/transport work is secondary to
this usable end-to-end release. Preserve its work and all seven unchecked criteria. Release evidence
must distinguish actual observations from mocks and missing measurements; disclose unavailable
independent comparison evidence rather than inventing scores or claiming an AI advantage.
No package/version/tag change, stable publication or new execution is authorized by this plan.

The first [#151 offline contract slice](GENERATED_REPAIR_CONTRACT.md) now prepares a fixed synthetic
request and validates caller-supplied source/test drafts with host-derived diff previews.
`authzest generation-preview` (`--json` optional) displays input only: it calls no model and executes
or applies nothing. The new scenario policy remains assistant-authored/pending maintainer review;
actual provider integration, genuine-generation acceptance and #152/#153 remain unfinished.

## Current baseline — 2026-11-05 KST

Release source: `090002d64d1ec5072c4e2ddf403a0e73e35d61ce`, package `0.1.0a4`, scan schema `1.2`,
tag [`v0.1.0-alpha.4`](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.4).
The prerelease was published on November 5 at 03:02:07 UTC; all six public files were downloaded,
checksum-verified and matched to the attempt-2 tag artifacts. The public macOS binary passed 13
scan/preview plus one fixed-runtime check; see the
[release receipt](../releases/RELEASING.md#alpha4-publication-and-public-asset-verification--2026-11-05-kst).
Normal documentation delivery is tracked in #83. Tag run attempt 1
failed with 4,923 Python tests passing and one fake-server JSONL race; unchanged-tag attempt 2 passed
4,924 Python tests, 71 Node tests and all eight jobs including publication. The post-alpha.4 source
change tracked under [#130](https://github.com/casing1/authzest/issues/130) atomically publishes
complete fake-server JSONL snapshots with strict record validation and deterministic regressions.
Its verification and delivery are tracked separately; it changes test reliability, not production
Codex behavior or live-AI acceptance. Published alpha.4 bytes and the failed first attempt are unchanged.
The earlier exact-source nonpublishing run passed seven jobs with publication skipped. Fresh source
installation and genuine alpha.3 replacement each passed 13/13 offline checks on one macOS/Python 3.12
host. These are not new live Codex or active owner-file observations.

The previous registered-template source scope is accepted; the new #150 course-release scope is not complete.
Native downloads are experimental scan/preview distributions, not verified consumer installers or
cross-platform active-file support. The earlier November 12–13 stable target is superseded by the
readiness gates below, not a delivery promise. New PoC/test and model-authored repair generation for
the single maintained scenario are required; general-repository support is not.

### Delivery history and preflight observations

The recorded bounded-core delivery baseline is `ee49f5a`, after
[PR #123](https://github.com/casing1/authzest/pull/123) delivered the bounded acceptance-status record
by normal merge and #82 → #81 → #35 were completed in order. Exact head `a24b859` passed ten CI checks;
both automatic reviews completed with no published findings or unresolved review threads. The security
review did not report a finding count, so this is not a zero-finding assessment. Six post-merge checks
passed. This completes the registered source-core scope, not general repository remediation,
independent evaluation or release-candidate acceptance.
The recorded installed observation remains bound to source `c868152`, after
[PR #120](https://github.com/casing1/authzest/pull/120) delivered the reviewed opt-in owned-file CLI and
[PR #121](https://github.com/casing1/authzest/pull/121) delivered its acceptance/capture runbook.
A separately approved installed happy path at that source completed recommendation, before/diff/apply/
after/restore with full original output and actual file verification. On 2026-11-02 KST the maintainer
accepted that bounded walkthrough, English/Korean limitations and existing offline failure/refusal/
user-edit/recovery and no-change/unknown evidence. This is a review decision, not a new live run or
release-candidate acceptance. PR #123 subsequently completed that status delivery as recorded above.
The earlier file-API observation remains bound to `fb90c46`, after
[PR #118](https://github.com/casing1/authzest/pull/118); do not transfer that observation to the new CLI.
[PR #114](https://github.com/casing1/authzest/pull/114) delivered #113's nonpublishing native preview
workflow. Its separately approved baseline run at `b5de9d9` passed all three hosted platforms' binary,
package and fresh-download checks; [the recorded run](https://github.com/casing1/authzest/issues/83#issuecomment-6484547184)
does not establish consumer installation/upgrades or acceptance of a later candidate.
[PR #115](https://github.com/casing1/authzest/pull/115) added an opt-in editor review workspace, not an
enforced security boundary or #89 risk acceptance. PR #116 added installed-CLI smoke: clean source
installation and same-version source replacement at `1d0ebb8` passed 13 checks each on one macOS host.
The [source-install record](../releases/RELEASING.md#local-source-install-observation--2026-10-29)
does not establish a versioned alpha.4 upgrade or other platforms/routes. Those historical observations
retain their original scope; the November 5 candidate checks below are separate.
The 2026-11-02 preparation sets the source version to `0.1.0a4` and proposes unused tag
`v0.1.0-alpha.4`, without tagging or publication. PR #125 delivered that preparation; PR #127 then
delivered the minimatch dependency repair at candidate `b5f3eb81d318e94c5e400ec52e78f1550e13f931`.
Both heads passed ten CI checks and both automatic reviews; each merged main passed six checks.
Dependabot #12 is fixed and #126 is complete, independently of #89. On November 5 the exact candidate's
[native preview](https://github.com/casing1/authzest/actions/runs/41946366368) passed 7/7 jobs: each of
Linux x64/macOS arm64/Windows x64 passed 26 selected/relocated, 13 packaged and 13 fresh-download
offline scan/preview checks. Three downloaded binary manifests also passed local checksum verification.
One-host disposable source installation and genuine alpha.3 → alpha.4 replacement each passed 13/13
offline installed-CLI checks with noneditable provenance/package-byte verification. No product AI,
policy/runtime worker, active-flow or UI check was added. These results belong to `b5f3eb8`, not later
documentation merges or the eventual release commit. The [current release-readiness matrix](../releases/RELEASING.md#alpha4-readiness--2026-11-05-kst)
separates source-only active owner-file operation from native scan/static UI/offline previews.
The [November 5 static recheck](https://github.com/casing1/authzest/issues/89#issuecomment-6647312400)
retains #89's `needs_review` / medium judgment. The maintainer subsequently
[accepted the named residual tooling risk for the forthcoming alpha.4 only](FORMATTING.md#alpha4-maintainer-disposition--2026-11-05-kst),
with visible warnings, guarded-command assumptions and follow-up. This is a release disposition, not
a parser fix, compatibility result or blanket waiver. PR #129 subsequently delivered the warnings at
`090002d`; all 211 tracked non-Markdown file modes/blobs matched the decision basis `7509a6a`.
The alpha.4-only decision is bound to that exact source in #83. #89 stays open; final release/public
readback is recorded separately above, not retroactively attributed to the earlier preflight.

The sharing/adapter source implementation was delivered through [PR #103](https://github.com/casing1/authzest/pull/103)
at merge `cc644a1` on 2026-10-25 KST. It builds on offline repair-recommendation delivery `8409bc7`,
merged through [PR #102](https://github.com/casing1/authzest/pull/102) on 2026-10-24 KST, and the
`536b412` main baseline after [PR #109](https://github.com/casing1/authzest/pull/109). The registered pair
was delivered at `cbe6b37` through [PR #101](https://github.com/casing1/authzest/pull/101) on 2026-10-21 KST. The earlier pair implementation
base `c12f4b137b30f96202b3a2555b3b5a151edf6e56` delivered the unchanged [pair design](OWNER_POLICY_REPAIR_PAIR_DESIGN.md) through
[PR #100](https://github.com/casing1/authzest/pull/100) on 2026-10-19 KST. The maintainer separately
approved its exact scenario/source pair/eight expected labels and the bounded pure registry/preview
slice in the [recorded decision](https://github.com/casing1/authzest/pull/100#issuecomment-6258235318).
The source implementation introduced in [PR #101](https://github.com/casing1/authzest/pull/101)
remains unreleased; its delivery records are tracked there. The separate
[repair-recommendation reference](../reference/OWNER_POLICY_REPAIR_RECOMMENDATION.md) now covers
the delivered offline contract and unreleased exact-sharing/adapter stage. One fresh, separately
approved live attempt at `cc644a1` on 2026-10-28 KST returned `recommendation-ready` /
`registered-change`, selecting the existing registered template with a host-derived diff and passing
offline revalidation; see the [bounded acceptance record](https://github.com/casing1/authzest/issues/81#issuecomment-6458726176).
The one-run approval is consumed. No policy execution, application or restoration occurred, and it
is not an independent benchmark or the completed remediation workflow. The maintainer subsequently
[approved the dedicated check design and offline implementation](https://github.com/casing1/authzest/pull/110#issuecomment-6459020000).
PR #110 adds the [single-candidate fixed-check Python API](../reference/OWNER_POLICY_REPAIR_CHECK.md)
and dedicated worker/transport, initially verified offline/static/with mocked processes at `510377c`.
A subsequent separately approved before-only run at that commit completed on 2026-10-28 11:49:55 KST:
six matches, the expected two mismatches, exit `0` and confirmed cleanup; see the
[acceptance record](https://github.com/casing1/authzest/pull/110#issuecomment-6460245210).
A later separately approved after-only run at documentation-only commit `7f9c5ce` completed on
2026-10-28 13:11:38 KST with eight matches, exit `0` and confirmed cleanup; runtime code was
unchanged from `510377c`. The [after record](https://github.com/casing1/authzest/pull/110#issuecomment-6460474112)
also documents offline comparison of captured bindings and the two expected true-to-false changes,
not a new comparison API. Both run approvals are consumed. Separately authorized final-head review
and delivery subsequently completed through PR #110 at `ea081e0` on 2026-10-28 13:52:15 KST, after
[both automatic reviews completed without findings](https://github.com/casing1/authzest/pull/110#issuecomment-6460924699)
on `c265bf1`. Embedded after is not applied-file verification; the separate file-bound API and
its later observation are described below. At that checkpoint #81/#35/#82 remained open; their later
bounded completion is recorded above. #80 is unchanged.
The earlier original design was delivered at `f1cbd2fdcfc91453488ac38bbd53ac2a14940b7e` through
[PR #98](https://github.com/casing1/authzest/pull/98) on 2026-10-16 KST. These are recorded bases,
not claims about latest main. Design head `a170d82` passed ten CI checks and completed
[code/security automated reviews without reported findings](https://github.com/casing1/authzest/pull/98#issuecomment-6206327402).
The earlier #80 delivery through [PR #97](https://github.com/casing1/authzest/pull/97) at `38587c3`
passed ten final-head CI checks and both code/security re-reviews, then six reported post-merge checks.
#77 and #80 are closed. The source implementation introduced in [PR #99](https://github.com/casing1/authzest/pull/99) provides #81 S1's
[offline recommendation data API](../reference/OWNER_POLICY_RECOMMENDATION.md), not the full #81
workflow or a published feature. The unchanged [original design](OWNER_POLICY_IMPROVEMENT_DESIGN.md)
remains the historical proposal delivered through PR #98. Implementation CI/review/delivery
outcomes are tracked separately in PR #99. The separate
[2026-10-16 S1 continuation](https://github.com/casing1/authzest/issues/81#issuecomment-6206079101)
does not approve all #81 extensions or authorize provider calls, policy execution or patches.
The [historical evaluation inventory](EVALUATION_INVENTORY.md) completed
[#108](https://github.com/casing1/authzest/issues/108) through PR #109. It checks existing artifact
bytes and preserves their distinct provenance; it does not select or freeze a new benchmark.
#84's independent-review attestation and measured comparison remain open.

### Supporting evaluation work — secondary to the course-release priorities

The following inventory preserves #84's delivered preparation and remaining conditions. Its local
next-step descriptions are not the overall release priority and do not replace #151–#153 or #85.

The [evaluation protocol](EVALUATION_PROTOCOL.md) now records the user's November 6 direct acceptance
of the current exact 21 reference values across seven assistant-authored scenarios. The v1 snapshot
at `tests/fixtures/evaluation_reference/v1/` fixes source, questions, splits, reference values and
scoring math; its raw task/reference copies intentionally preserve the original pending proposal
metadata. The new manifest records `accepted-current-reference-values` from
`direct-user-chat-confirmation`, recorded by assistant, not authenticated identity, human authorship
or an all-rationale/citation inspection. `independent_review_attested` remains false. Earlier positive
reactions/preparatory merges are not retroactively relabeled as approval.
The unchanged split is three development/four reserved, with four restricted/two mixed/one public
policy values. The single reserved public control is not balanced coverage, a secret/unseen holdout
or a runtime guarantee. Source-checkout preflight uses `python -m scripts.evaluate_reference`
(`--json` optional); `--control` builds task-only all-unknown synthetic responses before references
are loaded, not a static baseline or model-quality result. The existing pure math remains separate
from this pinned offline reference adapter. v1 changes need a new reviewed v2, not refreshed hashes.
Next collect the missing independent/inspection review evidence and separately fix any live prompt,
model/configuration and repeat budget. `live_benchmark_ready` remains false; no live model/source/
worker/workflow execution, release or risk acceptance is added. Historical artifacts remain unchanged,
and all seven #84 checklist items remain pending.

The offline comparison contract supplies `scripts/evaluation_response.py`'s strict, task/request-bound
response and `python -m scripts.evaluation_comparison` paired input plan. Evidence-assisted alone gets
partial in-memory single-module declarations; source/policy/questions/answer formats/draft instructions
otherwise match, and expected answers/review metadata stay outside provider payloads. The evaluator
plan is not provider input. `--dry-run` uses synthetic null answers in all three mode slots, not a real
static baseline or model comparison; `--fault missing`/`invalid` requires dry-run and preserves failures.
The registered static-answer adapter now supplies explicit task-digest-bound declaration queries,
not expected answers or general natural-language interpretation. Use
`python -m scripts.evaluation_comparison --static-only` (`--json` optional) for a separate source-only
observation of the fixed seven owned tasks; stage all responses before reference loading. It derives
source counts/direct scopes from existing parser observations, abstaining on coverage/diagnostic/
composition uncertainty and always on policy/runtime questions.
The mapping was developed with exposure to public v1 tasks/references: staging answers before
reference loading is not independent/blinded/unseen evaluation. Report only a descriptive static
observation of these fixed tasks, not general benchmark performance or model value. Dry-run remains
all-synthetic; `--static-only` cannot combine with it or its fault injection. Independent review evidence, live
configuration/repeat freeze and actual model comparison remain next steps. v1/raw/math/history/product
versions and all seven #84 checks stay unchanged; no AI/worker execution, patch, risk acceptance or
release is added.

An offline trial-candidate helper now makes proposed model/effort/repetition/timeout settings and
paired application messages explicit: `python -m scripts.evaluation_trial_plan` requires all four
arguments; see the [protocol](EVALUATION_PROTOCOL.md#offline-ai-trial-candidate-not-execution).
It plans 14/28/42 slots for one/two/three repetitions but does not collect from/run a provider, query an account or
freeze a live configuration. Message hashes/IDs do not grant consent or response freshness, and schema
`0.1` still cannot bind configuration/repetition. Keep the separate static observation, public-data
exposure, missing independent review and answer-only metric limits visible. Next review the candidate
and design the missing live bindings/context/collection controls; live sharing/execution remain false.
v1/math/history/product versions, risk decisions, releases and all seven pending #84 checks are unchanged.

The separate `scripts/evaluation_collection.py --dry-run` helper now validates synthetic host-receipt
batches with the four explicit planner settings, preserving every mode/repetition denominator and
missing/invalid/reported-failure routing. Fresh local namespaces and strict batch bindings are not
provider evidence: rewrapped old inner JSON can pass, caller-supplied provenance is unverified and
duplicate rejection is one-batch-only. No receipt/log file import, provider transport/capture, actual
model/context verification or scoring is implemented. The
[proposed provider-capture design](EVALUATION_TRANSPORT_DESIGN.md) now separates a model-visible
invocation/request-response `0.2` candidate from unchanged inner `0.1` answers. Runtime capture,
isolation and failure policies are still proposals; nonce echo is neither authentication nor provider
freshness. The owned pure codec is now available in `scripts/evaluation_invocation.py` for candidate
preview, strict outer `0.2` / inner `0.1` validation and synthetic dry-run only; it reads owned task
data without account/network/process/reference/scoring access. Original/final message hashes and
schema hashes stay separate, and raw response text is retained only in returned memory. This neither
verifies pinned App Server schema support nor proves provider freshness/runtime execution. The
[protocol](EVALUATION_PROTOCOL.md#offline-invocation-codec-continuation) documents required settings
and CLI examples. Owned recipe/frame builders and a serial offline `Batch` ledger are now available
through `scripts/evaluation_dispatch_recipe.py` and `scripts/evaluation_dispatch.py`. Fresh preview
namespaces/revision tickets and caller-supplied integer-nanosecond clocks model fixed TTL/window,
reserve/send/ack/finish and explicit cleanup assertions while retaining all denominators; they are
not authenticated approval, process observations, real timers or a persistent cross-process gate.
Selected owned generated-schema projections check candidate request shapes, not full protocol/
provider conformance; `remoteControl/status/read` uses `null`, not `{}`. See the
[dispatch protocol](EVALUATION_PROTOCOL.md#offline-dispatch-recipe-and-state-simulation).
The separate `scripts/evaluation_preflight.py` pure API now checks caller-supplied config results
against the narrow owned policy and compares discovery/generation MCP names with redacted counts.
It adds no CLI/RPC or Batch integration and changes no recipe descriptor. The
[source/startup review](EVALUATION_TRANSPORT_DESIGN.md) distinguishes merged config from runtime
catalog/provenance: plugin warmup is guarded when disabled, but other startup network effects remain
possible. No safe-launch or isolation verdict follows. Pure incremental JSONL/RPC checks and fixed
owned fake-server stdio/exit/timeout/cleanup tests now preserve that startup boundary; notification
payload semantics remain unvalidated. See the
[JSONL/fake-pipe scope](EVALUATION_PROTOCOL.md#pure-jsonlrpc-checks-and-owned-fake-pipes).
Separate pure helpers now check bounded detached boundaries and selected synthetic session/catalog/
thread/settings/final-answer candidates; they are not complete protocol/recipe coverage or actual
account/model entitlement. See the
[selected semantics scope](EVALUATION_PROTOCOL.md#selected-synthetic-response-semantics--not-a-trial).
Pure `SlotCoordinator` / `BatchCoordinator` now compose those unchanged checks with supplied
discovery/generation byte/EOF/exit/cleanup records and the original dispatch clocks/budgets.
Only `turn/start` marks model-send; exact RPC ack/lifecycle confirmation precedes finishing while
failure/skipped denominators remain. See the
[pure coordinator scope](EVALUATION_PROTOCOL.md#pure-slot-and-batch-coordination--not-live-transport).
The dispatch ledger is extended with `Batch.fail`: the bridge immediately latches an observed slot
failure at the current clock, preserving its first cause until cleanup instead of replacing it with
a later timeout; cleanup and secondary clock outcomes stay separate. Existing clock/TTL/`T`/window/
finish contracts are retained.
The 2026-11-09 test-only batch-pipe extension connects that bridge to the existing fixed fake peers,
checking send/ack/finish ordering, synthetic original-budget expiry, failure/cleanup and planned
denominators. It requires pipe closure and child reaping before finish; caller-controlled clocks
and fixture watchdogs remain test controls, not production timing or a live transport.
This is not live transport, a public launcher, authenticated approval or full recipe coverage; live
lifecycle/compatibility remain gates. Actual config/account RPC, production process/capture/isolation/timer/cancellation/cleanup
enforcement remain unimplemented; live trials still need explicit source/account/model/turn/time
approval and missing freeze/review evidence. Offline delivery is not actual-call approval or benchmark freeze.
This evaluation preparation does not expand the product adapter or change pinned `0.153.0`; v1/math/history, product `0.1.0a4` / report schema `1.2`,
live-freeze false, risk/release decisions and all seven pending #84 checks remain unchanged.

Historical records live in the [changelog](../../CHANGELOG.md), linked issues/PRs and
[release record](../releases/RELEASING.md); this plan records current priorities, not every past test count.

| Implemented                                     | Actual boundary                                                                                                                                                                                                                       |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Installed CLI, local API/UI and static parser   | Bounded FastAPI route/registration/local-inherited dependency declarations; no complete Python interpretation or authorization verdict                                                                                                |
| Evidence, proposal and expectation contracts    | Exact identities/references, draft expectations and read-only comparison; schema `1.2`                                                                                                                                                |
| Mock review/walkthrough and copy application    | Separate source/apply/check/restore decisions; new owned single-file POSIX copy, not arbitrary checkout editing                                                                                                                       |
| Opt-in App Server fixture workflow              | Pinned adapter, exact sharing approval; default AST check, separately approved fixed debug/health runtime option                                                                                                                      |
| Owned report policy example                     | Pure-policy developer tests and scanner inventory; authentication is unconfigured/fail-closed, no HTTP authorization acceptance                                                                                                       |
| Read-only owner Codex review (#75 / PR #76)     | Exact two-source sharing; one approved live run returned one host-valid answer / ten unexecuted cases, not a patch or security proof                                                                                                  |
| Readable CLI output (#79 / PR #90)              | Human-readable defaults, explicit JSON streams and complete sharing previews; no new AI authority                                                                                                                                     |
| Offline case-review / fixed-plan API (#77)      | Pure data with exact source/case/decision bindings; caller choices are not authenticated approval, and every plan is non-executable                                                                                                   |
| Fixed owned-policy check API (#80 / PR #97)     | Source-only fixed policy observations under a fresh one-use decision; Windows/frozen execution refuses; no HTTP/authentication proof                                                                                                  |
| S1 recommendation contract (PR #99)             | Pure data request/result validation and output-only preview; caller-supplied provenance, empty changes, no provider/policy execution                                                                                                  |
| Registered repair-pair API (PR #101)            | Exact registered data and host-derived one-file diff preview only; the pure API itself adds no observations or apply/execute capability                                                                                               |
| Repair recommendation / sharing (source)        | PR #102/#103 delivered; one historical separately approved live response selected the registered template and passed host validation; approval consumed, no apply or policy execution                                                 |
| Registered repair-policy check (PR #110 source) | Initial offline/mock checks, then separately approved before/after runs: expected two before mismatches and eight after matches; both approvals consumed, no CLI/UI or applied-file check                                             |
| Owned-file repair API (PR #118 source)          | Separately approved captured-before check, diff acceptance, apply, captured-after check and restore observed at `fb90c46`: 6/8 before, 8/8 after; restored copy and records retained; historical API, not installed CLI acceptance    |
| Owned-file CLI (#82 / PR #120)                  | POSIX non-frozen source only; installed happy path at `c868152` on one macOS/Python 3.12.7 host: before 6/8, exact diff/apply, actual applied-after 8/8, restored before / generation 3; bounded acceptance delivered through PR #123 |

The accepted historical core uses one registered synthetic policy pair, eight reviewed cases and Codex
template selection. New FastAPI PoC/test generation and model-authored repair source are **not implemented**;
the maintained single-scenario version is now required by #151/#152, while general repositories remain
out of scope. The historical acceptance is not independent evaluation or HTTP/authentication/DB enforcement.

The recorded owner review at `9257bd7` took about 74 seconds. On 2026-10-09 KST the maintainer
explicitly approved that exact envelope's ten labels: two allow and eight deny; see the separate
[review record](../../tests/fixtures/owner_case_review/maintainer_review.json) and
[#77 contract](../reference/OWNER_CASE_PLAN.md). Model authorship and the original envelope remain
unchanged. This labels-only decision is not authenticated execution consent and does not approve
the separate 28 assistant-authored developer-test labels or frozen evaluation set. The original
draft and offline plans remain not-run. A later separate historical recipe `1.0` #80 source check produced
[ten matching observations](../reference/OWNER_POLICY_CHECK.md#actual-source-acceptance--2026-10-09-kst);
authorization remains unknown. One later freshly and separately approved recipe `1.1` check at
`e037986` also matched all ten expectations, recorded
[separately](../reference/OWNER_POLICY_CHECK.md#current-coordinator-source-acceptance--2026-10-09-kst).
Both one-run approvals are consumed. Final-head review/CI and delivery subsequently completed in
[PR #97](https://github.com/casing1/authzest/pull/97) on 2026-10-15 KST, without another policy execution.
A host-valid response proves shape/reference checks, not correctness.

Historical [v0.1.0-alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3) remains
package `0.1.0a3`, schema `1.2`; the alpha.4 source/tag is identified above. Version output alone proves
neither release acceptance nor the contents of an older binary. Preserve the version-specific receipts.
Do not rewrite existing tags/assets. Windows supports scan; the current
fixture application/runtime mode is supported only on tested POSIX platforms.

## One milestone map

GitHub milestone numbers below are phase identifiers, not development-week numbers or exact release manifests.

| Phase                                       | Current status              | Completion gate / remaining tracking                                                                                                          |
| ------------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| 01 — CLI foundation and alpha.1 follow-up   | Closed; preserved           | Completed foundation history                                                                                                                  |
| 02 — Source evidence and alpha.2 follow-up  | Closed; preserved           | Completed evidence/release follow-up history                                                                                                  |
| 03 — Offline AI contract and evaluation     | Closed; preserved           | #33 contracts/mock evaluation; not actual model-quality results                                                                               |
| 04 — User-approved Codex workflow           | Open; bounded core complete | #77/#80 complete; PR #123 delivered bounded acceptance and #82 → #81 → #35 completion; milestone closure is separate from core acceptance     |
| 05 — CLI usability and prerelease readiness | Publication verified        | #79 complete; alpha.4/public readback complete; normal documentation delivery tracked in [#83](https://github.com/casing1/authzest/issues/83) |
| 06 — Evaluation and course delivery         | Open                        | #84 reviewed comparison and #85 reproducible demo/evidence freeze; source test-harness stability delivery tracked separately under #130       |

Authenticated reconciliation under [#78](https://github.com/casing1/authzest/issues/78) refined 04
and created 05/06. #79/#83 are assigned to 05 and #84/#85 to 06; verify their assignee, labels and
milestone fields. Closed 01–03 and historical item assignments are preserved. No due dates are invented. At audit start 04 had 31 closed issue/PR items
and two open issues; an item-count percentage is **not** product or effort completion. Keep closed
historical items in their original phases.

## Remaining backlog and order

| Priority                   | Focused issue                                                                         | Dependencies and acceptance boundary                                                                                                                                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Completed                  | [#79 readable CLI](https://github.com/casing1/authzest/issues/79)                     | PR #90 merged; offline formatter/fake-provider checks and exact sharing previews retained                                                                                                                                      |
| Completed                  | [#77 case review and fixed plan](https://github.com/casing1/authzest/issues/77)       | Exact ten-label approval recorded separately; original model history and non-executable offline plans preserved; closed by PR #97                                                                                              |
| Completed                  | [#80 fixed owned-policy harness](https://github.com/casing1/authzest/issues/80)       | PR #97 merged; separate recipe 1.0/1.1 source runs matched ten cases each; approvals consumed; exact-head CI/reviews complete                                                                                                  |
| Completed in bounded scope | [#81 bounded reproduction/remediation](https://github.com/casing1/authzest/issues/81) | PR #123 delivered accepted criteria; one registered pair/eight cases/template selection only. Preserve distinct file-API and installed-source evidence; general repository PoC/repair-source generation unimplemented          |
| Completed in bounded scope | [#82 integrated acceptance](https://github.com/casing1/authzest/issues/82)            | PR #123 exact-head checks/reviews and normal merge completed; #82 → #81 → #35 closed in order. One-host installed happy path and offline failure/refusal/recovery evidence are not native or independent evaluation acceptance |
| Publication verified       | [#83 alpha.4 release](https://github.com/casing1/authzest/issues/83)                  | Exact `090002d` published; attempt-2 checks/public files verified; normal documentation delivery tracked in the issue. #89 assessment and post-alpha.4 #130 source delivery are separate                                       |
| Source delivery tracking   | [#130 fake-server JSONL race](https://github.com/casing1/authzest/issues/130)         | Atomic complete-log publication and strict shared validation with deterministic regressions; retain transport/cancellation/cleanup assertions. Verification and normal delivery tracked in the issue; alpha.4 bytes unchanged  |
| Evaluation                 | [#84 measured comparison](https://github.com/casing1/authzest/issues/84)              | Freeze independently reviewed tasks/labels before prompt changes; use separate approved measurement scope. Core acceptance and historical development observations are not independent benchmark results                       |
| Delivery                   | [#85 demo/OSS evidence](https://github.com/casing1/authzest/issues/85)                | #82/#84 results or explicit unavailable evidence; distribution claims consistent with #83                                                                                                                                      |

#80's [fixed policy-check API](../reference/OWNER_POLICY_CHECK.md) is delivered with stale/declined/
expired/reused decision handling and unknown failure outcomes. #79 is complete and #77's exact ten
labels have been reviewed. Offline contract/mocked-process tests need no model call or actual policy
execution. Label approval does not authorize execution; any further observation requires a fresh,
separately bounded exact-plan decision. The recipe `1.0` and corrected `1.1` source-run approvals
are both consumed. Their retained observations are not new AI evidence or HTTP authorization proof.

#81 S1's source implementation introduced in PR #99 provides a separate pure recommendation
contract and read-only preview under the bounded continuation above. The registered request contains only the fixed policy source,
policy-only criteria and trusted-input assumptions. Cases, labels, observations, provider/model
claims and approval/execution fields are rejected, not silently accepted. The registry is empty;
`no-change` and `unknown` are valid data statuses, not verified fixes or security verdicts.
No filesystem/network/provider/process access, policy evaluation, CLI or patch capability is added.
The [reference](../reference/OWNER_POLICY_RECOMMENDATION.md) documents the implemented API and an
explicitly SCRIPTED `unknown` example. Implementation CI/review/delivery outcomes are tracked in
PR #99, separately from the unchanged design delivered through PR #98. That slice alone did not complete
#81; the later bounded workflow acceptance is recorded above.

S1 delivery subsequently completed through PR #99 at merge `4290d2d` on 2026-10-16 KST.
The unchanged historical [repair-pair design](OWNER_POLICY_REPAIR_PAIR_DESIGN.md) was delivered through
PR #100 on 2026-10-19 KST. The maintainer approved that exact test-only ownership-omission scenario,
its source pair and eight assistant-authored expected labels, separately from the next offline
registry/preview implementation slice. Authorship remains assistant-authored; this decision is not
an authenticated approval capability, observation or runtime consent.

The source implementation introduced in PR #101 provides the separate [registered pair API](../reference/OWNER_POLICY_REPAIR_PAIR.md)
with full fixed source/criteria/assumption/case data, a separate review-record binding and host-derived
one-file diff. This unreleased pure API does not call a provider, import/evaluate
the policy, access files/network, execute a process, apply a patch or produce observations. Its state
stays provider `0`, execution/application/restoration `not-run`, before/after observations null,
comparison `not-evaluated` and authorization `unknown`. Existing S1 schema `1.0`/`empty-v1` and
the #80 worker stay unchanged. The separate model-sharing, check and file-workflow APIs and their
independent approvals are described below; the pure pair API grants none of those effects. Do not treat this finite synthetic
regression as a production vulnerability or evaluation set. This pure API alone did not complete #81;
the later bounded workflow acceptance is recorded above.

PR #102 delivered the separate offline repair-recommendation contract: a fixed `before`/`after`
request, strict registered-change/no-change/unknown results and host-derived diff selection.
PR #103 delivered the separate `codex-owner-repair` command at `cc644a1`. Complete
source/prompt/schema/settings previews and a fresh exact sharing decision precede one pinned
App Server attempt; preview-only remains offline. Host transport metadata is not signed provider
provenance, and validated explanations/expected effects are not observed policy behavior.
Offline refusal, stale-sharing and scripted-response checks do not establish live acceptance. The
separate 2026-10-28 live attempt is recorded above and its one-run approval is consumed; the transport
remains unreleased. The maintainer approved the exact
[dedicated fixed-check recipe design](OWNER_POLICY_REPAIR_CHECK_DESIGN.md) and offline implementation.
PR #110 implements the [separate Python API](../reference/OWNER_POLICY_REPAIR_CHECK.md), complete fixed
plans, terminal expiring decisions and a dedicated worker/transport. Offline/static/mock tests do not
execute either candidate or provide runtime observations. The later separate before-only source run
at `510377c` produced the expected two mismatches and completed with confirmed cleanup; its approval
is consumed. The separate later after-only run at documentation-only `7f9c5ce` matched all eight
expectations with unchanged runtime code and consumed its own approval. Offline inspection of the
saved records confirmed matching shared bindings and only the two expected true-to-false changes;
this is not a new product comparison API or authenticated attestation. Another candidate run requires
fresh approval; no automatic paired execution or new CLI/UI is added.
The five-second startup/I/O/completion budget and one-second child cleanup budget are not a hard
whole-filesystem deadline or OS sandbox. Embedded after is a control, not applied-file verification.
PR #110's final-head review and delivery completed separately as recorded above. PR #118 supplies the
separately reviewed file-bound new-copy workflow below; existing `codex-owner-review`, S1 and the
#80 worker stay unchanged.

The maintainer approved the [owned-file repair design](OWNER_POLICY_FILE_REPAIR_DESIGN.md) at `29d8c82`.
PR #118 introduces the [source API](../reference/OWNER_POLICY_FILE_REPAIR.md): separate
before/diff/apply/after/restore decisions, one fresh private `policy.py`, checks of captured file bytes,
and preservation of user edits. Initial verification used temporary files and scripted processes.
On 2026-10-29 KST, a separately approved source-API acceptance at `fb90c46` observed the actual
copied-before bytes, accepted the exact diff, applied it, checked the actual copied-after bytes and
restored the copy. Before matched 6/8 expectations with the two intended over-allows; after matched
8/8. File binding, exit/cleanup and evidence persistence were confirmed. No new provider call was
made: the earlier recommendation was revalidated. The final copy is `restored-before` / generation 3;
the passing after comparison is historical, not a pass for the restored before file. See the
[exact file-workflow record](../reference/OWNER_POLICY_FILE_REPAIR.md#file-workflow-acceptance--2026-10-29-kst).
The old expired preparation ran no worker and remains separate. All actual stage approvals are
consumed. One macOS/Python 3.12.7 source observation is not CLI, cross-platform, HTTP or release acceptance.

The maintainer initially approved #82's **offline implementation only**. The
[`--file-workflow` CLI extension](../guides/OWNER_FILE_WORKFLOW.md) preserves recommendation-only
defaults and connects only the current validated response, after separate copy and five-stage
decisions. POSIX non-frozen preflight, original 300-second expiry, one-attempt limits, no-change/unknown
without a copy and honest partial/refusal/user-edit/recovery output remain required. Temporary-file,
fake-adapter and scripted-worker tests exercise coordination, not actual policy behavior. That initial
approval covered a draft PR and existing CI, not review activation, merge or live effects. Subsequent
separate authorization completed PR #120's final-head reviews and source delivery at `a0ae879`.

On 2026-10-30 KST, one noneditable Python 3.12.7 wheel installation had 64 package files matching
the source and passed the existing 13 plus 10 additional offline checks. This is one-host evidence,
not pipx, upgrade or native-binary acceptance. Two separately approved real recommendation attempts
then completed: the first declined its expired copy choice; the second created one copy and prepared
a before plan, then ended `before-check-declined`. Both exited `0`, with no policy worker, apply or
restore, and the original main remained clean. The second raw stdout capture was incomplete; separate
comparison of the full before plan, final workflow object, durable record and actual file does not
verify the whole stdout stream as one JSON document.

A later, separately approved installed happy path at `c868152` completed a current registered
recommendation, one private copy, captured before (6/8), exact diff/apply, captured actual applied-after
(8/8) and restore to exact before bytes / generation 3. Complete original stdout JSON, stderr and
private file/record bindings were checked; CLI/capture exited `0` and original checkout stayed clean.
The new installation again matched 64 package files and passed the existing 13 plus 10 offline checks.
See the [bounded installed observation and runbook](../guides/OWNER_FILE_ACCEPTANCE.md).

The maintainer accepted the bounded #82 evidence mapping and English/Korean walkthrough/limitations
on 2026-11-02 KST. Offline failure/refusal/user-edit/recovery and no-change/unknown tests remain separate
from the recorded installed happy path; acceptance is not live failure injection or a new run.
PR #123 then delivered the acceptance-status documentation after its required exact-head checks,
separately approved automatic reviews and normal merge `ee49f5a`; #82 → #81 → #35 were completed in order.
At that November 2 checkpoint, all one-run allowances were consumed and independent #83/#84/#85/#89
remained open. No new execution, file effect, risk acceptance or release followed from that record.

Implemented #79 defines human-readable defaults and explicit JSON compatibility: one final result on stdout
in JSON mode, interactive previews/prompts/progress on stderr, and one complete preview for preview-only
JSON. Preserve exact identity-bound sharing content before consent; summaries alone are insufficient.
The guides document the default-output migration rather than claiming unchanged stdout behavior.

The source core's bounded #35 completion does not satisfy #83 automatically. Keep the implemented
scope and source/native limitations explicit; a documentation merge or passing mock is not a release gate.

After alpha.4, prioritize #150's genuine generation, approved verification and local result presentation
(#151–#153), alongside #85's reproducible course demo. Broader #84 benchmarking is secondary, not a
reason to postpone the usable workflow; missing independent evidence must stay explicit.
Keep the earlier `b5f3eb8` preflight, exact `090002d` release checks and `c868152` live observation
separate. Neither release packaging nor historical development cases constitute fresh held-out model
evaluation. Limit work to the maintained scenario and local results UI rather than broad native support,
cloud deployment or additional adapters. A stable candidate needs its own final checks and a fresh #89 assessment/disposition;
the alpha.4-only risk decision must not carry forward. Retain #130's deterministic test-log
regressions in the source candidate; repeated release retries are not a replacement for a repair.

## Core acceptance and defensive PoC

The checked items below retain the earlier registered-template acceptance. They do not complete the
new generation/verification/UI requirements, which remain separately unchecked.

- [x] Exact ten-case label review recorded separately on 2026-10-09 KST (#77); offline contracts exist, but plans remain non-executable and execution consent is separate.
- [x] Readable CLI results, retained records and documented text/JSON streams accepted (#79 / PR #90).
- [x] #80 source-only fixed harness delivered through [PR #97](https://github.com/casing1/authzest/pull/97), with exact-head CI/code/security reviews complete on 2026-10-15 KST. Source observations are not endpoint authorization evidence.
- [x] Separately approved #81 file-API sequence observed at `fb90c46` on 2026-10-29 KST: before 6/8, exact diff/apply, after 8/8, restore and retained records; no new AI call or installed CLI acceptance.
- [x] Separately approved installed-source happy path observed at `c868152` on 2026-10-30 KST: current recommendation, before 6/8, exact diff/apply, actual applied-after 8/8, restore, complete original JSON and retained evidence; one macOS host only.
- [x] Reviewed bounded defensive reproduction and evidence-linked registered remediation/no-change accepted on 2026-11-02 KST (#81); not general repository PoC or repair-source generation.
- [x] Final bounded installed-flow/walkthrough, bilingual limitations and existing offline failure/refusal/user-edit/recovery/no-change evidence mapping accepted on 2026-11-02 KST (#82); not new live execution.
- [x] PR #123 acceptance-status documentation passed exact-head checks and separately approved automatic reviews, merged normally at `ee49f5a`, and completed #82 → #81 → #35 in order on 2026-11-02 KST. This covers bounded source acceptance only.
- [ ] Newly generated defensive PoC/test and AI-authored one-file repair for the maintained FastAPI scenario accepted (#151); not a registered-template choice.
- [ ] New isolated execution design and separately approved before/after controls, exact-diff refusal/application, stale-edit protection and recovery accepted (#152).
- [ ] Actual scan/PoC/diff/check/recovery results available in the local React UI, with execution and consent initially kept in the CLI (#153).
- [ ] Frozen independent reference review and measured evaluation, or explicit unavailable evidence, recorded (#84).
- [ ] Exact stable distribution claims, reproducible installed demo, multilingual README and minimum course evidence accepted (#150/#85), with a fresh candidate-specific #89 disposition.

In the historical #77–#82 workflow, “PoC” meant local synthetic **defensive regression reproduction**
for an owned pure policy: model-authored cases were data consumed by a fixed reviewed harness, not
AI-written Python/shell execution. Those observations do not test HTTP authentication, dependencies,
DB or real endpoint enforcement. The new #151 scope instead requires a newly authored defensive test
for the maintained FastAPI scenario; running it needs the new #152 design and separate exact-plan
approval. Neither an old approval nor a child process alone supplies OS/network isolation.

The current correct policy must allow a no-change/unknown result. The exact clearly labelled,
intentionally incorrect test-only pair and eight labels were reviewed on 2026-10-19 KST; that review
does not authorize runtime observation or patch application. Do not invent a production vulnerability
to force a patch or extend this approval to changed bytes/cases.

Source sharing, exact-case label review, exact-diff approval/application, before/after checks and restore
are separate bound decisions. Changes to relevant source/cases/plan require fresh decisions. Planning
approval, tool permission or an earlier live run cannot authorize them. Record applied/checked/restored/
failed/not-run/unknown distinctly and preserve originals and later user edits.

## Schedule: readiness gates within the remaining submission buffer

The seven **development** weeks agreed on 2026-09-10 include work already done; this audit does not
start a fresh seven-week plan. The original remaining-calendar estimate is historical, not a current
submission date. The maintainer estimates submission around **2026-11-18**, not a confirmed fixed
deadline. The missed November 4 alpha.4 target and earlier November 12–13 stable target are historical,
not current promises. The published alpha.4 receipt remains unchanged. Work in this gate order and
retain time before submission for exams, fixes, recording/report preparation and rehearsal:

| Order       | Work / gate                                                                                                                                                                                                             |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First       | Freeze the one-scenario generation contract and new execution design (#151/#152), then implement without assuming permission for real model calls or generated-code execution.                                          |
| Next        | Obtain separately approved observations of the generated PoC/repair workflow and independent controls; deliver the local result UI (#153) and reproducible instructions in parallel where contracts are stable.         |
| Candidate   | Complete #85's demo/minimum evidence and README translations, exact-source regressions/install/artifact checks including #130, and fresh #89 stable-candidate disposition. State unavailable #84 measurements honestly. |
| Publication | Select a stable version/tag and publish only after candidate findings, demonstrated required scope and release/public-download gates pass. There is no automatic date-based promotion of alpha.4.                       |

Foundation/evidence/contracts and recorded live integration already consumed the early development
budget. A stable course release means the newly declared single-scenario generation, approved
verification and local presentation are complete and demonstrable, not general repository support or
a production security guarantee. If a mandatory gate fails, report the gap and revise the plan with the
maintainer; do not silently redefine template selection as generation or manufacture stable readiness.
Additional live model use, source sharing and active file stages still require their own bound decisions.

## Deliberately deferred

General nested dependency/callable interpretation, broad authentication/security classification,
multi-file/existing-checkout repair transactions, arbitrary repositories/apps/unrestricted generated-code
execution, additional adapters, cloud deployment, GUI execution/approval controls and signing/notarization
remain deferred. This does not defer #151's one-file patch plus generated test, #152's specifically
approved isolated execution, or #153's local results UI. Open a separately justified issue before
expanding that scope. The static parser
still needs maintained regressions, but finishing a complete deterministic vulnerability engine is
not a dependency of the Codex improvement demo.

## Working rules

Use focused issue → short-lived branch → meaningful implementation/tests → bilingual docs → PR →
exact-head required CI and resolved review conversations → merge commit. Assign casing1, relevant
existing labels and a verified milestone to every issue/PR; #1 deliberately spans phases without a
single milestone. Preserve historical authorship and approvals. Mark criteria complete only when
actually satisfied and merged; do not inflate commit counts.

English documents require Korean counterparts; the root README additionally requires Japanese and
Russian. Update guides only for implemented behavior and keep links/commands/status/limitations aligned.
Ordinary development, standard checks, configured PR reviews and normal merge proceed through the
required gates without a new per-attempt confirmation. This does not bypass product source-sharing,
case-review or file-stage consent, exact-candidate residual-risk decisions, or publication gates.
Historical approval records remain unchanged. See [contributing](../../CONTRIBUTING.md) and [branch rules](BRANCH_RULES.md).
