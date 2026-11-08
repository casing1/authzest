<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/ko/CHANGELOG.md">한국어</a>
</p>

# Changelog

[Documentation index](docs/README.md) · [Release guide](docs/releases/RELEASING.md)

All notable changes to AuthZest are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) while the project remains in initial development.

## [Unreleased]

### Added

- Add pure incremental JSONL framing and a serial RPC inbox in `scripts/evaluation_jsonl.py`,
  with bounded shared input/notification budgets and closed envelope/correlation checks. Allowed
  notification payload semantics remain unvalidated. Add tests using only an owned fixed Python
  fake server over stdio, including exit/timeout/cleanup paths; this is not a provider launcher,
  production transport, OS sandbox or enforcement of the evaluation slot budget. Include the pure
  test file in the existing Windows CI command, not the POSIX process tests or a recorded CI result.
  No CLI/log import,
  Batch/preflight integration, real account/model/server/policy worker, scoring or runtime evidence
  is added. Semantic config/catalog/thread/turn verification and coordinator lifecycle remain next.
  Product/pin/recipe/codec/v1/math/history/versions and all seven pending #84 checks stay unchanged;
  live/readiness/authorization/freeze flags remain false, with no risk acceptance or release.

- Add pure offline `scripts/evaluation_preflight.py` configuration checks and discovery/generation
  comparison with bounded JSON input, exact owned recipe values, closed supported paths, explicit
  bounded MCP maps and redacted counts. Unknown extras are unsupported, not a claim of protocol
  invalidity; opaque origins/MCP bodies prove no complete schema or runtime provenance. This adds
  no CLI, launch/RPC/account/model/timer/worker access, log import or Batch integration and changes
  no existing recipe descriptor. Startup/source review remains distinct from supplied config checks;
  separate fake-JSONL/parser/lifecycle work must retain that explicit boundary. Product/pin/v1/math/
  history, live-freeze false and all seven pending #84 checks remain unchanged; no actual AI/worker
  call, risk acceptance, readiness approval or release is added.

- Add pure offline `evaluation_dispatch_recipe` descriptor/frame candidates and an
  `evaluation_dispatch` serial simulation ledger with fresh previews, revision tickets, explicit
  reserve/send/ack/finish transitions and retained failure/skipped denominators. Caller-supplied
  integer-nanosecond clocks exercise the 300-second confirmation TTL, fixed dispatch window,
  original preview anchors and never-reset slot budget; synthetic decisions/cleanup are not runtime
  evidence or authenticated approval. Selected owned generated-schema projections correct
  `remoteControl/status/read` params from `{}` to `null`; `initialized` has no params. They do not
  prove complete protocol/provider conformance. No account/RPC/process/timer/cancellation/cleanup
  enforcement, persistent cross-process gate, scoring or live freeze is added. Next review effective
  configuration/discovery semantics before separate fake-process transport work. Product/pin/v1/math/
  history and all seven pending #84 checks remain unchanged; no AI/worker call, risk acceptance or release.

- Specify the [evaluation-only transport recipe and whole-batch decision](docs/development/EVALUATION_TRANSPORT_DESIGN.md).
  Locally generated normal/`--experimental` `0.153.0` protocol schemas review field syntax only,
  without server/account/model RPC; runtime configuration, tool isolation, nested `outputSchema`
  and provider compatibility remain unverified. Propose a 300-second confirmation TTL, a bounded
  batch dispatch window, sequential slots and stop-on-first-nonvalid without retry/resume/extension.
  Executable transport/decision state/API remains unimplemented: next are pure offline batch-decision/
  state tests, then separate fake-process transport tests. Existing codec/pin/product/v1/math/history,
  live-freeze false and all seven pending #84 checks are unchanged; no actual AI/worker call,
  risk acceptance or release is added. Design delivery is not live-execution approval or benchmark freeze.

- Implement the owned pure offline invocation codec in `scripts/evaluation_invocation.py`: preview
  model-visible `0.2` candidates, validate strict outer responses plus unchanged inner `0.1` answers,
  and exercise synthetic dry-runs without provider capture. Separate original/final message hashes
  and schema hashes; retain bounded UTF-8 raw response text in returned memory, not a log import or
  canonical-inner-as-original claim. Schema shaping is only a subset; the strict decoder remains
  authoritative and pinned App Server support is unverified. Echoes/rewrapped answers prove no
  provider freshness; provenance stays caller-supplied/unverified and runtime-observed false.
  Preserve the original transport proposal as history with a current codec continuation. Next review
  versioned transport recipes/batch expiry, then fake-process tests. No live transport, account/
  network/process/reference access, scoring, live freeze, risk acceptance or release is added.
  Existing `0.1` modules/product adapter/pinned `0.153.0`, v1/math/history, product `0.1.0a4` / report
  schema `1.2` and all seven pending #84 checks stay unchanged. Verification/delivery is separate.

- Propose the [evaluation provider-capture boundary](docs/development/EVALUATION_TRANSPORT_DESIGN.md)
  in English/Korean: candidate model-visible invocation/request-response `0.2` wraps unchanged inner
  `0.1` answers. Direct runtime capture, isolation and failure handling are proposals, not implemented
  transport. A nonce echo is not authentication or provider freshness; design CI/merge is proposal
  delivery, not execution approval or benchmark freeze. Next is a pure offline codec, followed by
  separate transport/fake-lifecycle tests. Keep the product adapter/pinned `0.153.0`, v1/math/history,
  product `0.1.0a4` / report schema `1.2`, live-freeze false and all seven pending #84 checks unchanged.
  No actual call, risk acceptance or release is added.

- Add offline synthetic host-receipt batch validation in `scripts/evaluation_collection.py` with
  required dry-run/planner settings, fresh local namespaces and strict expected-slot/inner-`0.1`
  bindings. Preserve missing/invalid/reported failures, reject even identical invocation duplicates,
  and report unmatched routing separately without changing denominators. Bound receipt/batch bytes
  and submission count. Old whole receipts fail, but rewrapped old inner JSON can pass: provenance
  remains caller-supplied/unverified and provider freshness false. This is neither persistent one-use
  enforcement nor authentication/consent. No provider capture/model verification, live collection,
  reference scoring, receipt/log import, live freeze, execution, risk acceptance or release is added.
  Existing payloads/response contract, v1/math/history/product versions and all seven pending #84
  checks are unchanged. Verification and normal delivery are separate.

- Add source-checkout-only `scripts/evaluation_trial_plan.py` to prepare explicit model/effort/
  repetition/timeout candidates and canonical paired application messages with content hashes and
  byte lengths. All four settings are required; labels are syntax-only, not catalog/account checks.
  Seven cases/two AI modes describe 14/28/42 slots for one/two/three repeats, not executed calls.
  Deterministic order is not randomized or fully counterbalanced; nominal timeout sums are not hard
  time/usage caps. IDs are metadata, not consent or schema-`0.1` configuration/repetition freshness.
  No transport/collection, fresh-context/tool enforcement, effective wire-context verification, live
  configuration/prompt/repeat freeze, sharing/execution, independent evaluation or model result is
  added. Existing payloads/contracts, v1/math/history/product versions, risk/release decisions and
  all seven pending #84 checks remain unchanged. Verification and normal delivery are separate.

- Add a source-only registered static-answer adapter for the fixed seven owned evaluation tasks.
  A task-only digest registry stores explicit declaration queries, not expected answers; derive
  source counts/direct `Security` scopes from existing in-memory parser observations and abstain on
  coverage/diagnostic/composition uncertainty, unregistered tasks and all policy/runtime questions.
  Exclude inherited scopes/provider graphs and keep distinct source declarations, including deferred
  factories, separate from runtime claims. Add `python -m scripts.evaluation_comparison --static-only`
  and `--static-only --json`; stage all responses before loading references. The default command still
  prepares a plan; paired AI inputs and synthetic-only dry-run behavior remain unchanged. Static-only
  excludes dry-run/fault injection.
  Mappings were developed with public v1 task/reference exposure, not independent/blinded/unseen
  holdouts; answer staging before reference reads does not remove that limitation. No measured
  outcome is recorded in this entry. No model-quality claim, live comparison, independent-review attestation, live freeze,
  AI/worker execution, patch, risk acceptance, release or completed #84 criterion is added here.
  v1/raw references/math/history/product source/schemas/versions stay unchanged; verification/delivery
  is recorded separately.

- Add an offline evaluation response contract (`scripts/evaluation_response.py`, schema `0.1`) and
  paired comparison plans via `python -m scripts.evaluation_comparison`. Bind strict whole-case JSON
  responses to task-only task IDs and mode/payload-derived request IDs; preserve canonical empty
  CSV versus null and missing/invalid failure kinds. Share source/policy/questions/answer formats/
  development-draft instructions, adding only partial in-memory single-module declaration evidence
  to evidence-assisted; keep evaluator references/metadata out of provider payloads. The evaluator
  plan is not provider input. `--dry-run` stages all three modes' synthetic-null responses before
  references load; optional missing/invalid faults affect one case per mode without dropping
  denominators or crediting invalid unknowns. That [PR #137](https://github.com/casing1/authzest/pull/137)
  slice added no real static-answer adapter, model-quality result, live configuration/repeat freeze,
  independent-review attestation, provider call or source execution.
  v1/raw references/math/history/product schemas/versions and all seven #84 checks remained
  unchanged; no risk acceptance or release. Verification and normal PR delivery are separate.

- Record the November 6 direct user confirmation of the current exact 21 reference values and add
  `tests/fixtures/evaluation_reference/v1/` with raw task/reference copies and a separate pinned
  decision manifest. Preserve assistant authorship and historical pending proposal metadata; record
  current reference-values acceptance separately, not authenticated identity, signed/human authorship,
  all-citation inspection or independent review (`independent_review_attested` remains false).
  Pin source/questions/splits/reference values/math, with new reviewed v2 required for changes.
  Add source-only `python -m scripts.evaluate_reference` preflight and an optional `--control` that
  stages task-only all-unknown synthetic responses before references load. This is not a static
  baseline/model result or a complete live-benchmark freeze: prompt/model/configuration/repeat budget
  remain unfixed and `live_benchmark_ready` false. No actual AI/source/worker/workflow execution,
  release, risk acceptance or completed #84 checklist item is added; verification/delivery is separate.

- Add source-checkout-only, candidate-independent pure metric mathematics in
  `scripts/evaluation_metrics.py`, with exact canonical answers, whole-case invalidation and retained
  denominators, count-weighted family/split summaries and null unmeasured fields. Scope its unit
  tests to unrelated synthetic data with `python -m pytest tests/test_evaluation_metrics.py`.
  Clarify the earlier English/Korean deferral: at that checkpoint actual candidate integration/scoring,
  freeze and the comparison harness awaited exact-label review; this standalone mathematics did not approve
  labels or consume the real seven-scenario/21-question candidate. No data/binding, historical
  artifact, product command/schema, provider/runner integration, live comparison, measured model
  result, release or #84 acceptance completion is added. Verification and normal delivery are separate.

- Append a maintainer-requested public-intent control before evaluation freeze; this draft places it
  in reserved evaluation.
  Preserve the original six scenarios/18 proposals and their splits exactly; the revised candidate has
  seven scenarios/21 assistant-authored references, three development/four reserved and four
  restricted/two mixed/one public policy proposals, not balanced coverage. Update English/Korean
  review status and measurement denominators. At that checkpoint all 21 answers awaited exact review;
  the earlier positive reaction approved neither the original 18 nor the new three. That control-addition
  slice added no freeze, scorer/comparison-harness implementation, measured result, live call,
  release or #84 completion.

- Initially prepare a separate source-checkout evaluation draft in
  [PR #133](https://github.com/casing1/authzest/pull/133) for [#84](https://github.com/casing1/authzest/issues/84):
  six new owned-source data scenarios and 18 assistant-authored reference proposals, all awaiting exact
  maintainer review and not frozen. Add a bounded, read-only preflight and human/JSON review packet;
  keep task-only inputs separate from references and bind each draft to its canonical input identity.
  Document three-mode comparability, fixed denominators and separate declaration/intent/unknown,
  citation and workflow measures in English/Korean. Preserve all historical evaluation bytes and
  approvals. This adds no benchmark result, new scorer/live adapter, product AI/worker call, reference
  approval, release or completed #84 criterion.

### Fixed

- Publish the offline fake Codex server's complete JSONL event-log snapshots atomically for
  [#130](https://github.com/casing1/authzest/issues/130), instead of exposing append writes to polling
  readers. Reuse strict UTF-8, newline-framing and completed-record JSON validation in the parent
  reader and successive fake-server generations. Preserve cancellation, phase-diagnostic and child
  cleanup assertions; add deterministic visibility, failure and malformed-record regressions.
  This test-only, serialized-writer contract provides atomic visibility, not fsync durability,
  multiwriter coordination or a sandbox. It does not change production Codex parsing, product
  runtime, package/schema versions or the published alpha.4 tag/assets, repair the historical
  failed tag attempt, or establish new live-AI acceptance. All 25 new deterministic log tests passed;
  transport/full regression and normal PR/CI delivery are recorded separately in #130.

### Changed

- Record the verified alpha.4 publication in a postpublication documentation follow-up without
  changing its tag, package/schema version or assets. Align four README languages, English/Korean
  release records, indexes and current development/model priorities; preserve historical observations
  and source-only active-file limits. Plan conditional November 10–11 RC and November 12–13 stable
  targets around #130's test-harness repair, #84/#85 evidence and final checks, with November 14–17
  reserved for submission buffer. The alpha.4-only #89 decision is not stable-release clearance.
  Normal documentation delivery is tracked in #83 without changing the published release bytes.

## [0.1.0-alpha.4] - 2026-11-05

Published as [v0.1.0-alpha.4](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.4) on
2026-11-05 at 03:02:07 UTC, from `090002d64d1ec5072c4e2ddf403a0e73e35d61ce`, package `0.1.0a4`,
unchanged scan schema `1.2`. November 2 in the immutable tag was package preparation, not publication.
[Tag run 41957416243](https://github.com/casing1/authzest/actions/runs/41957416243) attempt 2 passed
all eight jobs, 4,924 Python and 71 Node tests. Attempt 1 failed with 4,923 passing tests and one
fake-server JSONL race, tracked separately under [#130](https://github.com/casing1/authzest/issues/130);
the unchanged-tag rerun did not fix it. All six public assets matched checksums and tag artifacts;
the public macOS binary passed 13 scan/preview plus one fixed-runtime check. See the
[exact receipt and limitations](docs/releases/RELEASING.md#alpha4-publication-and-public-asset-verification--2026-11-05-kst).
No actual model call, arbitrary target execution or user-source patch was part of these release checks.
Keep packaging evidence separate from historical live acceptance at `c868152` and independent
#84/#85 evaluation/course evidence. #89 remains OPEN under its alpha.4-only residual-tooling decision.

The entries below preserve each development checkpoint's scope and status. Earlier descriptions of
pending issues or unreleased slices describe those checkpoints, not a new run or the final release state.

### Changed

- Record the November 5 maintainer decision to accept only #89's residual developer-formatting
  availability risk for the forthcoming alpha.4, with visible four-language README and English/Korean
  contributor/formatting warnings. Retain guarded-command assumptions and direct CLI/editor/API gaps;
  keep #89 open and `needs_review` / medium unchanged, not fixed or attributed to user fault. Reassess
  on an upstream shipped-byte fix, new exposure/impact/guard bypass, relevant tooling changes or the
  next release. Bind the exact warning candidate in #83 after normal merge and non-Markdown byte
  comparison against decision basis `7509a6a821947b516f543222d7cd620ab2ad8e83`. This is not a future
  blanket waiver, dependency/code change, new product AI/worker run, tag or publication; other release
  gates remain separate.

- Record the November 5 nonpublishing preflight at exact candidate `b5f3eb8`:
  [native preview](https://github.com/casing1/authzest/actions/runs/41946366368) attempt 1 passed 7/7 jobs;
  Linux x64/macOS arm64/Windows x64 each passed 26 binary, 13 packaged and 13 fresh-download offline
  scan/preview checks, and the three downloaded executable manifests matched. A one-host disposable
  fresh source install and genuine alpha.3 → alpha.4 replacement each passed 13/13 installed-CLI checks
  with noneditable provenance/package-byte verification. Preserve the earlier different-scope records;
  do not transfer these observations to the documentation merge or eventual release commit.
  Refresh the four README languages, English/Korean release plan and completed-core index status.
  The conditional November 4 target passed without publication; #83/#89, final release/runtime,
  other consumer routes and public-asset gates remain. No product AI/policy-worker call, risk acceptance,
  package/schema change, tag or release is added.

### Release scope

- Readable CLI output by default, with explicit `--json` for scripts and separate interactive previews.
- Offline proposal/declaration previews and a bounded Codex owner-policy recommendation/file workflow.
  The accepted core covers one registered synthetic policy pair, eight reviewed cases, Codex selection
  of a registered template and a POSIX non-frozen source installation. It does not generate new PoCs
  or arbitrary repair source for general FastAPI repositories; active owner-file execution is unsupported
  in native executables and Windows.
- Bounded core delivery completed through PR #123 and ordered #82 → #81 → #35 completion on
  2026-11-02 KST. Independent evaluation, course evidence and distribution acceptance remain separate.
- PR #125 prepared an unused package version and aligned four README languages without a new
  provider/policy run, dependency change, risk acceptance, tag or release. The later minimatch
  maintenance below changes the candidate dependency graph; existing approval/refusal boundaries stay unchanged.

The entries below retain the scope and status of each development checkpoint since alpha.3. References
to an unchanged package version, pending issues or an unreleased slice describe that checkpoint, not
the candidate's current status. Historical observations are not reruns on this candidate.

### Added

- Reconcile [alpha.4 readiness](docs/releases/RELEASING.md) after PR #123's reviewed delivery and
  ordered #82 → #81 → #35 completion. Separate accepted POSIX source-CLI core evidence from portable
  scan/preview capabilities, final versioned candidate, consumer install/upgrade and publication gates.
  Refresh the dated [#89 static tooling assessment](docs/development/FORMATTING.md#current-static-recheck--2026-11-02-kst):
  the inspected official Prettier 3.9.10 still embeds brace-expansion 5.0.6 on the selected paths;
  `needs_review` / medium confidence and the exact-candidate disposition gate remain. No dependency,
  runtime, package/schema version, release asset or risk-acceptance change is made.
- Record [bounded maintainer acceptance](docs/guides/OWNER_FILE_ACCEPTANCE.md#bounded-maintainer-acceptance--2026-11-02-kst)
  on 2026-11-02 KST of the existing installed walkthrough, English/Korean limitations and separate
  offline failure/refusal/user-edit/recovery/no-change evidence. Align four READMEs, indexes, roadmap
  and #82/#81/#35 criteria without claiming a new live run or issue closure. The accepted core is one
  registered synthetic pair/eight cases, Codex template selection and the POSIX source CLI; general
  FastAPI PoC generation and model-authored repair source are not implemented. Final status-document
  checks, separately approved reviews and normal merge precede ordered issue completion. Independent
  #83/#84/#85/#89, published alpha.3, package/schema versions and runtime permissions are unchanged.
- Record one separately approved [installed owned-file CLI happy path](docs/guides/OWNER_FILE_ACCEPTANCE.md#installed-happy-path-observation--2026-10-30-kst)
  at source `c868152` on macOS/Python 3.12.7: current registered recommendation, one private copy,
  captured before check (6/8), exact diff/apply, captured actual applied-after check (8/8), then verified
  restoration to before / generation 3. Complete original JSON, stderr and file/record bindings were
  checked privately; original checkout unchanged. Earlier preparation/capture gaps remain historical.
  This is not live failure-injection, general repository remediation, native/upgrade acceptance or
  closure of #82/#81/#35. Published alpha.3, package/schema versions and #83/#89 gates are unchanged.
- Add the opt-in [`codex-owner-repair --file-workflow` source CLI](docs/guides/OWNER_FILE_WORKFLOW.md)
  for the current validated recommendation and existing owned-copy session. Keep recommendation-only
  defaults, separate sharing/copy/five-stage choices, original 300-second expiry and one-attempt
  boundaries; retain partial/failure/user-edit/recovery states. Show readable eight-case summaries and
  a single JSON stdout result with complete interactive previews on stderr. Temporary-file, fake-adapter
  and scripted-worker checks are offline, not new provider/worker observations or operational patch
  acceptance. #82/#81/#35 and release gates remain open; published alpha.3 is unchanged.
- Record the separately scoped [owned-file source API acceptance](docs/reference/OWNER_POLICY_FILE_REPAIR.md#file-workflow-acceptance--2026-10-29-kst)
  on main `fb90c46`, 2026-10-29 KST: captured-copy before check, exact-diff acceptance, apply,
  captured-copy after check and restore. Before matched 6/8 expectations with the intended over-allows
  for `non-owner` and `exact-owner-no-normalization`; after matched 8/8. Both checks exited `0`,
  cleanup and file/evidence state were confirmed, and the retained final record reports
  `restored-before`, generation `3`. The earlier recommendation was revalidated without a new AI call.
  This is POSIX non-frozen source API acceptance on macOS/Python `3.12.7`, not HTTP authorization,
  installed-CLI or native-binary acceptance. Align the four READMEs and the next #82 installed-CLI
  integration step; broader #81/#35, #89 and release gates remain open. Published alpha.3, package
  version and report schema are unchanged; this records no new release or revision of historical
  recommendation-only and embedded-control observations.
- Implement the unreleased source-only owned-file repair Python API from the approved design:
  explicit private-copy creation, separate expiring one-attempt decisions, captured-source worker
  protocol, file-state-bound checks and restoration, retained records and fail-closed recovery.
  Pure-data, AST, temporary-file and fake-process tests cover the new flow; no actual new-worker
  observation, operator patch acceptance, CLI integration, AI call or release is added in this slice.
- Propose the English/Korean design for #81's owned-file repair session: separate before/diff/apply/
  after/restore decisions, a fresh one-file copy, checks executing captured registered bytes and
  user-edit-safe restoration. Link it from the indexes, plan and existing control-check reference.
  This is a design for review; no implementation, worker run, patch acceptance or release is added.
- Align all four project READMEs with the implemented unreleased owner-repair command and separate
  source-only policy-check API. Correct stale PR #110 delivery status in English/Korean guides and
  update the preparation plan with the approximate submission date and existing native/pipx evidence.
  Preserve historical observations, published alpha.3, unfinished file-bound remediation and #89's
  separate risk decision; this documentation alignment does not change a version or publish alpha.4.
- Add an explicit installed-CLI smoke mode with 13 offline scan/preview checks and no launcher
  relocation or installer side effects. Record disposable macOS pipx source installation and
  alpha.3-source-to-main same-version replacement in the English/Korean release guide, with separate
  installed-byte provenance checks. Keep versioned upgrade, other platforms, native installation,
  final-candidate acceptance and #89 disposition open; no package version or publication change.
- Add an opt-in VS Code review workspace with automatic-formatting/Prettier defaults disabled and
  English/Korean contributor guidance for guarded formatting. Preserve personal editor settings and
  document overrides and unreviewed-PR limits; data-contract tests do not validate a running editor,
  replace the bundled parser, resolve #89 or accept release risk.
- Add a manual-only, exact-main-SHA native preview preflight for Ubuntu/macOS/Windows with read-only
  repository permissions, selected/relocated and checksum/download preview smoke, and short-lived
  run-bound test artifacts. Keep runtime execution and publication in the separate unchanged release
  workflow. Implementation/offline tests are not platform-run evidence, #89 risk acceptance, a version
  change or a release; English/Korean release guidance describes separate run approval and remaining gates.
- Extend the versioned offline release smoke with human/JSON registered owner-repair previews for
  both before/after candidates, alongside owner-review previews. Compare complete packaged data,
  prompt/schema/limits and exact human summaries with the checkout baseline, and require fresh
  identities across preview kinds, candidates and relocated copies. Binary mode has 26 checks;
  checksum-aware artifact mode has 13. No Codex call, policy execution, patch approval or release
  is implied; native-platform, clean-install and upgrade evidence remain separate gates.
- Record one separately approved after-only control run at documentation-only `7f9c5ce` on
  2026-10-28 13:11:38 KST, with unchanged runtime source from `510377c`: eight matches, zero
  mismatches, comparison `passed` / `cases-match`, execution `completed`, exit `0`, all cleanup
  confirmed and saved-record revalidation passed. See the [bounded record](docs/reference/OWNER_POLICY_REPAIR_CHECK.md).
  Pure-data comparison of captured records confirmed shared bindings and only the two expected
  true-to-false changes; it adds no product comparison API or authenticated attestation. Both candidate
  approvals are consumed. No before rerun, AI/network call, patch, review activation, merge or release;
  #80/historical artifacts remain unchanged. Final-head review/delivery needs new approval, then a
  separately reviewed file-bound apply/check/restore design; #81/#35/#82 remain incomplete.
- Record one separately approved before-only repair-policy source run at `510377c` on
  2026-10-28 11:49:55 KST: six matches and the expected two mismatches (`non-owner`,
  `exact-owner-no-normalization`), comparison `failed` / `case-mismatch`, execution `completed`,
  exit `0`, all cleanup confirmed and output revalidation passed. This is the intended incorrect-before
  demonstration, not worker failure; see the [bounded record](docs/reference/OWNER_POLICY_REPAIR_CHECK.md).
  The one-run before approval is consumed. At that checkpoint after remained unapproved/unexecuted;
  the separate later after observation is recorded above. Provider zero, authorization unknown, patch/restoration not-run; historical
  hashes and #80 unchanged. Host records are unauthenticated; no applied-file assurance, merge or release.
- Add #81's [registered repair-policy check Python API](docs/reference/OWNER_POLICY_REPAIR_CHECK.md)
  under the reviewed PR #110 design: explicit before/after candidates, complete source/case/worker/recipe
  plans, separate terminal expiring one-attempt decisions and a dedicated bounded worker/transport.
  Preserve strict observations versus expectations, separate child/workspace cleanup and unknown
  failures. Initial implementation verification at `510377c` was offline/static/memory-only mocked
  process behavior, not actual worker/policy execution; the later separate before/after acceptances
  are recorded above. POSIX source only; no new CLI/UI, provider call, applied-file verification,
  patch, merge or release. #80 stays unchanged; #81/#35/#82 and final-head delivery remain open.
- Add #81's first offline [owner-policy recommendation contract](docs/reference/OWNER_POLICY_RECOMMENDATION.md),
  schema `1.0`: one registered policy snapshot, policy-only criteria and fixed trusted-input assumptions.
  Validate caller/scripted `no-change` or `unknown` data with exact evidence bindings, strict closed
  fields and whole-artifact budgets; rebuild detached, read-only previews with an empty change-pair
  registry and no changes/diffs. Cases, labels, observations, provider/model claims and patch/approval
  fields are excluded. No provider, source evaluation, filesystem access, new CLI, patch or release;
  valid shape is neither model provenance nor a security verdict. Broader #81/#35 remains incomplete.
- Record one freshly and separately approved exact #80 source check on 2026-10-09 KST:
  macOS arm64/Python `3.12.7`, ten matching observations (two allow/eight deny), aggregate `passed`,
  child exit `0` and confirmed cleanup. Preserve the separate
  [observed record](tests/fixtures/owner_case_review/observed_check.json) and
  [exact plan/worker identities](docs/reference/OWNER_POLICY_CHECK.md#actual-source-acceptance--2026-10-09-kst).
  Scripted control-plane answer, no new AI call, provider zero, authorization unknown, patch not-run.
  The one-run permission is consumed; original draft/offline plans remain not-run and no Windows/
  frozen-binary/HTTP acceptance is claimed. Final-head #80 CI/reviews were pending at that checkpoint;
  delivery subsequently completed through [PR #97](https://github.com/casing1/authzest/pull/97)
  on 2026-10-15 KST without another policy run or release. The later corrected recipe `1.1`
  observation remains in its [separate record](tests/fixtures/owner_case_review/observed_check_recipe_1_1.json).
- Add #80's unreleased [fixed owner-policy check API](docs/reference/OWNER_POLICY_CHECK.md):
  separate exact-plan, caller-recorded, expiring one-use decisions; one pinned pure-policy worker;
  expected/observed/null outcomes with unknown failures. POSIX Python source only; no new CLI,
  model/HTTP/database calls, patches or release. This is bounded process control, not a sandbox.
  No actual policy execution is approved by the ten-label review.
- Record the maintainer's explicit 2026-10-09 KST approval of #77's exact ten-case envelope in a
  separate [review record](tests/fixtures/owner_case_review/maintainer_review.json): two allow,
  eight deny, labels only. Preserve original model authorship and SHA-256; this is not an
  authenticated receipt, execution consent, approval of other label sets or a runtime result.
- Add #77's pure [owner-case review/fixed-plan contract](docs/reference/OWNER_CASE_PLAN.md), schema
  `1.0`: retain exact model-authored inputs, original labels/evidence and source/task identities;
  record pending/approved/changed/declined caller choices without authenticated approval claims.
  Preview exact maintained policy bytes, selected labels and a pinned design recipe, revalidating
  all relationships after changes. No CLI/executor, provider call, case execution or release;
  the ten real labels are separately reviewed as recorded above; all offline plans remain
  not-run/authorization unknown and non-executable.

- Record one successful, freshly approved owner-review source-CLI run on 2026-10-01 at `9257bd7`:
  `draft-ready`, exit `0`, about 74 seconds, one answer and ten host-valid defensive case drafts.
  Provider-reported usage was 7,994 input / 2,242 output tokens, one warning and zero retry notifications.
  Keep model-authored expectations unreviewed, execution not-run and authorization unknown; no retry,
  fallback, patch or target execution. Synchronize all four README languages and English/Korean guides.
  This completes narrow provider acceptance, not broader #35 or a release; alpha.3 remains unchanged.
- Add source-only owner-review contract alignment: fixed `validation-*` reason codes within the
  existing three-field failure diagnostic, prompt `owner-policy-review-v2`, supported schema
  constraints and offline schema-versus-host conformance cases. Codes expose the first failed rule,
  not rejected values or provider text. Keep strict host-only evidence, uniqueness, UTF-8 and global
  budget checks, plus the `response-invalid` fallback. The full 2,451-test offline suite and
  531-test portable subset passed on 2026-10-01; phase-synchronized timeout regressions avoid startup-speed dependence;
  the offline implementation adds no provider call, live-compatibility claim, merge or release. The changed sharing envelope
  requires fresh approval; both historical approvals remain consumed.
- Record a second, separately approved source-CLI owner-review attempt on 2026-09-30 at `324505d`:
  `review-failed`, exit `1`, after about 84.8 seconds, with `response-validation` / `response-invalid`
  and `turn_start=acknowledged`. No draft was accepted; returned identity, usage and warning/retry
  counts remain unknown. The raw response was not retained, so the exact rejected condition is unknown.
  The unchanged public-source sharing envelope and one-turn/120-second limit were used, without
  AuthZest retry, model fallback, source execution or patch application. Source hashes and the original
  checkout were preserved. Those two attempts were unsuccessful; the subsequent offline alignment
  and separately approved 2026-10-01 success are recorded above. Earlier exact rejection causes remain unknown.
- Add source-only redacted failure diagnostics for `codex-owner-review` on 2026-09-28: a nullable
  `failure` object with allowlisted `stage`, `code` and `turn_start` strings, plus offline regressions.
  Distinguish local send attempts from acknowledged turn-start replies without exposing raw provider
  errors, logs, identifiers or partial output, or inferring billing, completion or failed-run usage.
  Preserve cancellation, version/sharing limits and no-retry behavior. This offline implementation
  itself does not reconstruct the 2026-09-24 failure or add a live result; subsequent evidence is recorded separately.
- Add #75's [`codex-owner-review`](docs/guides/CODEX_OWNER_REVIEW.md): a full offline JSON preview
  on all supported OSes and an exact-envelope sharing decision before a read-only, pinned Codex
  App Server request on POSIX. Use only two packaged owner-policy source snapshots, explicit policy
  and static evidence, not the independent case labels or arbitrary paths. Validate evidence-linked
  review answers and 1–16 non-executable defensive case drafts; expected values remain model-authored
  and unreviewed, execution not-run and authorization unknown. The first separately approved live attempt
  on 2026-09-24 at `c5be74d` returned `review-failed` after about 98.8 seconds, without an accepted
  draft or known usage. No AuthZest retry, patch application or target/generated-code execution occurred.
  Subsequent attempts are recorded above; another provider attempt needs fresh approval. Existing fixture workflows
  and published alpha.3 are unchanged; the guide records the bounded result and remaining unknowns.
- Add #73's source-checkout [owned report policy example](docs/guides/OWNER_POLICY.md): default-deny
  pure policy requiring authenticated identity, the exact reports:read scope and matching ownership,
  with an independent assistant-authored regression matrix and separate non-importing source inventory
  checks. The FastAPI reference has deliberately unconfigured fail-closed authentication and is not
  executed. Developer policy unit tests do not add a product runtime mode, provider use or a general
  authorization verdict. Frozen AI corpus, fixture allowlists, package version and alpha.3 remain unchanged.
- Add #71's read-only [`review-demo`](docs/guides/REVIEW_DEMO.md): combine one packaged mock case's
  exact diff, evidence, expectations, source declaration comparison and identity-bound prose test draft.
  The draft is a non-executable maintainer template, not model output or an observed runtime result.
  Compose entirely in memory, including on Windows, with no input files, temporary directories,
  provider calls, subprocesses, patch application or target execution. Existing fixture workflows,
  artifact schemas, package version and published alpha.3 are unchanged; broader #35 remains open.
- Add #69's offline [`proposal-check`](docs/guides/PROPOSAL_CHECK.md) source declaration comparison:
  revalidate an existing preview bundle, compare supported single-source before/after snapshots with
  caller-authored dependency-count or declared-scope targets, and retain identities and reasons in
  text/JSON results. Unsupported or ambiguous evidence remains unknown; policy intent is not evaluated.
  Completed processing/exit zero is not a match or security pass. No provider, source execution,
  embedded-path reads, patch application or approval is added. This source implementation is not in
  published alpha.3 and does not complete broader #35.
- Add #65's packaged offline [`fixture-demo` walkthrough](docs/guides/FIXTURE_DEMO.md): a fixed mock
  proposal, separate apply/source-check/restore decisions and retained private-copy records without
  repository fixture files, Codex, accounts, network calls or fixture-source execution. It initially
  requires supported POSIX operations and adds no target, bundle, runtime or automatic-approval option.
  This source addition is not in published alpha.3 and does not complete broader #35.
- Add #63's read-only [`proposal-preview` CLI](docs/guides/PROPOSAL_PREVIEW.md): validate a strict
  schema `1.0` bundle, then display the exact diff, linked evidence, expected outcomes and limitations
  as text or ASCII-escaped JSON. Add a caller-authored offline exporter, bounded POSIX regular-file
  input and platform-independent pure bundle APIs. Status remains draft/not-run; no provider calls,
  approval, patch application or test execution. This source addition is not in published alpha.3.
- Add #61's pure [expectation manifest](docs/reference/EXPECTATION_CONTRACT.md), schema `1.0`:
  bind caller-authored policy/declaration targets to the exact request, review, proposal, baseline
  registration and before/after source hashes. Validate typed expectations and same-request evidence;
  previews remain draft/not-run with unknown authorization. No generated tests, provider calls,
  CLI integration or new execution/approval authority; published alpha.3 remains unchanged.

### Changed

- Extend #83's versioned release smoke with offline owner-preview human/JSON envelope, packaged
  source/task, identity, summary and fresh-nonce checks for selected/relocated binaries and verified
  artifacts. Use a minimal preview-child environment without ambient credentials or Codex on PATH;
  retain dependency-free artifact verification and add Windows smoke-driver regressions. Binary
  mode now has 18 checks, artifact mode 9. No model call, label approval, policy execution or release;
  this does not establish clean-device installation, all-platform native acceptance or OS isolation.

- Make #79's `codex-owner-review`, `codex-fixture` and `fixture-demo` readable by default; reuse safe
  section/diff formatting in proposal preview/check and review demo. Scripts must add `--json` for
  one final stdout result, including application failures, with full interactive previews/prompts on
  stderr; offline owner-preview JSON remains one complete envelope. Preserve fields, unknown values,
  mock/model provenance, retained records, exit codes and separate exact approvals. This is an
  unreleased display/stream migration, not a new provider call, GUI, execution permission or release.

### Fixed

- Override standalone frontend `minimatch` from `10.2.6` to exact `11.0.1` for Dependabot alert #12,
  [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) / CVE-2026-118764.
  This deliberately crosses the `^10.x` ranges of ESLint, `@eslint/config-array` and
  `@typescript-eslint/typescript-estree`; scoped inspection found no use of v11's removed `makeRe`/`AST`
  APIs in those consumers, not general major-version compatibility. Add only the required transitive
  `@isaacs/nonrecursive-glob-match` `1.0.3`, keeping direct pins, package `0.1.0a4` and schema `1.2` unchanged.
  Ten focused regressions passed: locked/installed consumer resolution, CJS/ESM tiny-cap
  preprocessing bounds, ordinary globs/partial/Windows-path behavior, ESLint file traversal and
  TypeScript project-service allow/deny behavior. Maintenance is tracked in
  [#126](https://github.com/casing1/authzest/issues/126).
  These use bounded inputs and an immediate comparison sentinel, not a DoS load test. Inspected consumers
  use default optimization level `1`; AuthZest exploitation remains `needs_review` / medium, not a confirmed
  runtime bug. A zero-result npm audit covers the dependency graph only, not embedded copies. Prettier's
  independent #89 copy remains unchanged; final-head CI/reviews and the revised candidate's release gates
  remain pending. No risk acceptance, native workflow, tag or release is added.
- Update lint tooling's transitive Zod lock entry from `4.5.4` to `4.6.7` (#106) for
  [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5), without changing direct
  dependency pins or ESLint configuration. Pick up upstream's leading collection upper-bound check
  ([#6652](https://github.com/colinhacks/zod/pull/6652)). Tiny-input regressions, separate from normal
  frontend lint, record bounded union errors changing from `too_big` to `invalid_union`; the diagnostic
  follow-up ([#6662](https://github.com/colinhacks/zod/pull/6662)) is not included in `4.6.7`.
  This addresses the locked dependency warning, not a proven AuthZest runtime exploit; no
  resource-exhaustion stress test was performed. Schemas without an upper bound,
  including downstream React Hooks options potentially supplied through inline ESLint settings,
  remain unbounded and receive no automatic protection. The earlier #104 Zod note records that
  update's scope; this change does not give broader security clearance or resolve the independent
  Prettier #89 follow-up.
- Update the exact frontend development Vite pin from `8.2.2` to `8.2.4` (#104) to pick up bundled
  `launch-editor` `2.14.2` fixes for upstream
  [GHSA-698v-4r3x-3vcv](https://github.com/advisories/GHSA-698v-4r3x-3vcv),
  [GHSA-587h-7wmj-h5pm](https://github.com/advisories/GHSA-587h-7wmj-h5pm) and
  [GHSA-r825-w8mm-5pxw](https://github.com/advisories/GHSA-r825-w8mm-5pxw).
  This developer-tooling update does not establish an AuthZest runtime exploit; the normal Python
  UI serves built assets. Windows/WSL exploit reproduction was not performed. Residual Zod findings
  remain separate.
- Update the frontend development lock's `source-map-js` from `1.2.1` to patched `1.2.2` for
  [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) (#94), within PostCSS
  `8.5.26`'s existing `^1.2.1` range. Keep direct versions unchanged, with no override or new dependency,
  and add bounded checks for locked/installed copies, Vite-to-PostCSS resolution and normal map/CSS
  operations. The AuthZest product exploit path remains unproven (`needs_review`); Vite's default
  `devSourcemap: false` does not exclude earlier map parsing.
- Route repository Markdown and frontend formatting through a bounded EditorConfig/target guard
  ([#89](https://github.com/casing1/authzest/issues/89)); retain the reviewed root configuration and use
  an explicit empty Prettier options file. This is a scoped developer/CI mitigation. Prettier's bundled
  brace-expansion 5.0.6 remains separate from the 5.0.12 lock entry; residual follow-up remains under
  #89/#83, without a reproduced DoS or demonstrated AuthZest runtime flaw. See the
  [formatting boundary](docs/development/FORMATTING.md); package version, tags, and alpha.3 stay unchanged.
- Update the frontend development lock from brace-expansion 5.0.9 to 5.0.12 for three public DoS
  advisories (#87), retaining direct dependencies and minimatch 10.2.6. This changes developer/CI
  dependency selection, not a confirmed endpoint vulnerability or the immutable alpha.3 binaries.
  Prettier's embedded copy is not replaced by this lock entry; #89 tracks the separate
  EditorConfig path after the scoped #87 maintenance merge. A clean npm audit of the dependency graph is not evidence that bundled copies
  or every developer-tooling DoS path are safe.
- Bind owner-review confirmation to a fresh local invocation nonce, with a separate stable content
  identity. Reject a captured phrase from an identical prior invocation before constructing an adapter;
  revalidate the same nonce for the current single attempt. Add offline stale-phrase and actual-CLI
  fake-provider regressions. Full suite: 2,463 passed; portable subset: 542 passed. No CLI nonce
  override, new provider call or changed model task payload.
- Normalize logical source labels to POSIX form when comparing proposal baseline evidence on
  Windows, without changing legacy scan display paths or registration identities. Add nested-label
  regressions and a scoped Windows CI job; the file-reading CLI remains POSIX-only.
- Keep `fixture-demo` verification-setup failures in the session record as not-run with no execution
  attempt; show an explicit warning for unconfirmed journal persistence, retain the separate restore
  choice and exit nonzero. Unexpected exceptions escaping verification no longer synthesize a check result.
- Preserve confirmed-created workspace paths and initialization stages through shared constructor
  failures/cancellation, and report them in `fixture-demo` without deleting retained files or claiming
  a complete journal or resume support.
- Extend that failure handling in #67 to `codex-fixture` source/runtime modes and the development
  runtime script: persist setup failures as not-run without an execution attempt, warn about unconfirmed
  journals, retain initialization path/stage information and keep restoration separately approved.
  Unexpected exceptions escaping verification become workflow failures without fabricated check results
  or an automatic-restoration guarantee. Codex library cancellation still propagates; CLI interruption
  outside a prompt exits `130`, while intentional prompt decline/cancel behavior is unchanged.
  No provider or execution scope is added, and published alpha.3 assets remain unchanged.

### Documentation

- Record the maintainer's 2026-09-24 approval of the owner-policy criteria separately from pending
  independent review of the 28 assistant-authored expected labels and separate live-usage consent.
- Synchronize all four README languages and English/Korean guides after verified alpha.3 publication
  in #58. Record immutable source, main/tag workflows, public asset hashes and observed checks; preserve
  historical evidence and the remaining broader #35 scope. No tag, asset or package-version change.

## [0.1.0-alpha.3] - 2026-09-12

Published as [v0.1.0-alpha.3](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3), with package
`0.1.0a3`, from commit `99be6f5614d283befa2a421b64f84958b680f92f`. The
[release record](docs/releases/RELEASING.md) documents three-platform gates and public-asset verification.
Scan report schema remains `1.2`; this release does not enable arbitrary repository execution.

### Added

- Add #54's separately approved [owned-fixture runtime check](docs/guides/RUNTIME_VERIFICATION.md).
  `--runtime-check` selects the exact-plan gate; the default remains source-only configuration.
  Only byte-identical bundled constants execute, checking `app.debug` and one in-process ASGI health
  response. Retain five-second execution and separate one-second cleanup limits, scoped runtime
  evidence, conflict-aware restoration and journal schema `1.2` for runtime sessions.
  Add explicit optional `fixture` dependencies and native/downloaded-artifact runtime smoke gates.
  No arbitrary source/commands, exploit reproduction, automatic installs or security-fix claim.
  One newly approved source-CLI live draft/apply/runtime/restore check passed on `ce2834c` on
  2026-09-12, with the assistant entering exact phrases under bounded user authorization.
- Add #52's optional, separately approved source-configuration check between fixture-copy application
  and restoration: exact-plan approval, a fixed AST configuration worker with pinned source hashes, a 5-second timeout and 4 KiB
  output limit. Report `passed`/`failed`/`not-run` separately from restoration, while runtime verification
  stays `not-run`. No target source, model-generated command, or provider is executed by this check;
  this offline addition is not runtime/security-fix verification or new live-model evidence.
- Add #50's [Codex fixture command](docs/guides/CODEX_FIXTURE.md), introduced in source and now included
  in alpha.3's supported POSIX binaries: pinned App Server 0.153.0,
  exact-request sharing approval before process launch, at most one application-issued turn, and a narrowly
  validated debug-setting draft with separate apply/restore decisions for a fresh POSIX copy.
  One owned-fixture live draft/apply/restore check passed on `42ff108` on 2026-09-12, preserving the original.
  The assistant entered approval phrases under user authorization, not independent human review.
  General repository AI remains unimplemented; that historical check did not run verification.
  The default scan stays offline and parent #35 remains open for broader acceptance.
- Handle narrowly validated same-turn Codex stream-recovery notifications without issuing another turn.
  Accept at most three observed notices within the existing time/byte/event limits; discard pre-recovery
  output and usage, require a fresh validated final response, and keep fatal errors fail-closed.
  The notice count is not a provider-attempt or billing cap. The live check observed zero retry notices;
  stream recovery remains offline-tested only.
- Add AI schema `1.1` for provider-managed nullable temperature while preserving numeric-temperature
  schema `1.0`, existing request identities and the numeric default. No token or monetary cap is implied.
- Add #48's [owned-fixture copy application](docs/guides/FIXTURE_APPLICATION.md): explicit terminal
  approval, consumed live-session decisions, current-file checks, atomic single-file replacement,
  retained snapshots/journal and separately confirmed conflict-aware restoration on supported POSIX.
  Original checkouts, live providers and verification execution remain untouched; #35 is incomplete.
- Add #46's offline proposal/decision schema `1.0`, binding exact replacements, original hashes,
  evidence, review identity, rationale and verification intent. Derive diffs from bound text and check
  explicit decisions, expiry and supplied current source without writing or executing anything.
  Include a caller-authored debug-configuration demo, not AI generation or a verified fix.
  See the [proposal contract](docs/reference/PROPOSAL_CONTRACT.md). #35 remains incomplete.
- Implement #33's offline AI schema `1.0`: selected, immutable source/registration evidence, exact-input
  approval checks, strict response/reference validation, configurable identity/provenance, and isolated
  mock review results. Disabled, invalid, failure, timeout, and cancellation paths preserve static scans.
- Add a frozen six-case, three-mode evaluation harness with evaluator-only labels, repeated trials,
  explicit metric denominators, and nullable unmeasured usage/human review data. Policy criteria were
  maintainer-approved; reference labels remain assistant-authored and code-checked. Mock scores do not
  demonstrate model performance. See the [offline contract](docs/reference/AI_CONTRACT.md).

### Changed

- Replace the unused `CodexFinding` adapter placeholder with untrusted JSON responses in #33. That step
  did not add a live adapter or change CLI/API behavior. The separate #50 command above does not change
  scan report schema, target execution, existing-checkout patching, or published alpha.2 artifacts.

### Documentation

- Require appropriate issue/PR labels, maintainer assignment, milestone matching or a documented
  cross-milestone exception, and metadata readback in contribution guidance and PR checklists.
- Synchronize the four README languages and English/Korean guides with the published alpha.2 artifacts,
  release evidence, and next #33/#35 work. Record the post-publication documentation follow-up in the
  release procedure. This documentation-only change does not alter the alpha.2 tag or binaries.

## [0.1.0-alpha.2] - 2026-09-10

Published as [v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2), with Python
package `0.1.0a2` and report schema `1.2`, from commit `7cc359acbb864ef6d31e3b536787857da4f7e09c`.
The [release record](docs/releases/RELEASING.md) links artifact checks and their limitations.
These improvements are included in alpha.2, not the alpha.1 binaries.

### Added

- Added binary release smoke checks for source-only examples, JSON/report parity, strict/invalid-input
  exits, and an isolated relocated executable copy. These do not replace clean-machine or upgrade checks.
- Added bilingual dated changelog validation alongside the tag/package-version check.
- Extended the report to schema `1.2` with `effective_dependencies`: supported FastAPI/APIRouter
  constructor and `include_router` declarations plus route-local evidence, preserving original positions
  and declaration levels across repeated/multi-app mounts. `dependencies` remains route-local and both
  lists remain excluded from registration IDs. Context order is not a runtime execution guarantee.
- Added a source-only inheritance example and regression coverage for composition, unresolved collections,
  local-field compatibility, and shared CLI/API output. No AI integration was added.
- Extended the report to schema `1.1` with route-local `Depends`/`Security` evidence from supported
  parameter defaults, inline `Annotated`, and decorator `dependencies`. Records original source locations,
  syntactic targets, known scopes, and unresolved reasons without classifying authentication/authorization.
  Existing registration IDs and fields were preserved; inherited analysis was deferred at that step and
  is now added above. Nested dependency graphs remain deferred.
- Added a source-only dependency example and CLI/API regressions for ordinary DI, scope limits, and
  strict partial-report behavior. No model calls or target execution were added.
- Added report schema `1.0` with structured source diagnostics and explicit `bounded`/`partial`
  analysis status, while retaining existing route fields and legacy parse errors. This schema version
  is independent of the Python package version. See the [report contract](docs/reference/REPORT_CONTRACT.md).
- Added deterministic source-registration IDs, original decorator and owner positions, application
  identity, outer-to-inner include chains, and explicit deferred function-body inventory. Same-path
  registrations remain distinct, including repeated calls on the same line.
- Added opt-in `scan --strict`: a partial report remains available but returns exit code 1. Default
  scan exits and local API HTTP 200 responses for produced reports remain compatible.
- Added a project-owned, four-file FastAPI inventory example with three expected routes and a checked-in
  report fixture; its regression test verifies source analysis without importing the example.
- Added a tested documentation checker and CI checks for local links, language counterparts, matching
  examples/checklists, and Markdown formatting.
- Resolved repository-local absolute and relative router imports, aliases, and module references without
  executing target source, preserving cross-file registration paths and original source locations.
- Composed literal same-file router and registration prefixes, preserving repeated registrations and
  route source locations while omitting unresolved paths. See the [parser scope](docs/reference/PARSER_SCOPE.md).

### Changed

- Grouped English guides by topic and translations by language with mirrored topic directories, updating
  the documentation index, contribution instructions, and repository links together.
- Clarified the final product goal as a Codex-assisted, user-approved defensive repair loop: review
  source evidence, propose regression-test drafts and a patch, obtain approval for the exact diff,
  apply approved changes, and report verification results. This loop is planned in
  [#35](https://github.com/casing1/authzest/issues/35), not implemented by the source-report changes.
  No live model calls, target-code execution, or patch application were added.
- Organized a seven-week development plan around stable source-evidence contracts and evaluations that
  can be repeated when AI models change, reserving the remaining four to five weeks for exams, delays,
  and submission preparation.
- Initially staged the roadmap around a CLI-first evidence/report milestone, separate authentication
  and authorization interpretation, and optional AI explanation before optional local regression
  execution; the final Codex repair-loop goal above now extends that earlier plan.
- Refreshed all four project README languages, added Korean counterparts for the remaining project guides
  and PR template, and introduced a bilingual documentation index and translation maintenance policy.
- Distinguished source-checkout features from published preview binaries and clarified optional dashboard
  installation and safe release-tag procedures.

### Fixed

- Applied ignored-directory names only below the explicitly selected scan root, so an eligible project
  is not skipped because its root or an ancestor is named `dist`, `node_modules`, or `.venv`.
- Parsed UTF-8 BOM and Python source-encoding declarations consistently in single-file and repository
  scans, while retaining diagnostics for invalid bytes and unsupported encodings.
- Printed repository-relative route locations and individual parse errors in the text CLI, preserving
  existing JSON fields and default exit codes. Clarified that Codex installation/login diagnostics do not
  enable AI analysis or become prerequisites for local scans.
- Distinguished unscanned, running, failed, empty, and partial dashboard results, displayed parse-error
  details, cleared stale results before a new attempt, and kept repeated route registrations distinct
  through unique row keys.
- Required statically recognized FastAPI or APIRouter owners before collecting route decorators,
  excluding unrelated objects and shadowed or reassigned names. See the [parser scope](docs/reference/PARSER_SCOPE.md).
- Provided explicit repository context to the GitHub Release publishing job.
- Wrote checksum manifests with portable LF line endings on every build platform.

## [0.1.0-alpha.1] - 2026-09-04

### Added

- Python core boundaries for analyzer, parser, runner, and optional Codex adapters.
- Typer commands for help, version, diagnostics, repository scanning, JSON output, and the local dashboard.
- FastAPI health and scan endpoints with a React, Vite, and TypeScript dashboard.
- Cross-platform PyInstaller builds with SHA-256 checksums.
- CI, CodeQL, contribution guidance, a security policy, and localized project guides.

### Security

- Restricted the HTTP scan endpoint to the workspace selected by the local process owner.
- Removed caller-controlled filesystem paths from the HTTP API contract.

[Unreleased]: https://github.com/casing1/authzest/compare/v0.1.0-alpha.4...main
[0.1.0-alpha.4]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.4
[0.1.0-alpha.3]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.3
[0.1.0-alpha.2]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2
[0.1.0-alpha.1]: https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1
