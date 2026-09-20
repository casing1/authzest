<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/REVIEW_DEMO.md">한국어</a>
</p>

# Offline integrated review demonstration

[Documentation index](../README.md) · [Source declaration comparison](PROPOSAL_CHECK.md) · [Fixture application walkthrough](FIXTURE_DEMO.md)

## Scope and availability

[#71](https://github.com/casing1/authzest/issues/71) adds `authzest review-demo` to the source
checkout after alpha.3. Use a source revision containing this change; the published alpha.3 binaries
do not contain the command. Package version `0.1.0a3`, scan report schema `1.2` and existing artifact
schemas are unchanged. Acceptance and merge status are tracked in the issue; this is not a new release.

This read-only command combines one packaged example's exact diff, linked evidence, expectations,
source declaration comparison and a non-executable defensive regression-test draft. All feature data
is built in memory: no input files, temporary directories, provider calls, subprocesses, target imports
or execution, patch application or artifact writes. The path has no POSIX file-reader requirement,
including on Windows. It does not change existing Codex, fixture application, verification or restoration flows.

## Run the demonstration

With the source [development environment](../../README.md#development-setup) active:

```bash
authzest review-demo --help
authzest review-demo
authzest review-demo --json
```

Only `--json` and help are accepted. There are no positional arguments or target, input, model,
apply, runtime, approval or export options, and no confirmation prompt. Text output shows the preview,
comparison, draft and limitations; JSON contains the same composed information. Output is ASCII-escaped.

The maintained source-only case changes one `Security` declaration's `scopes=[]` to
`scopes=["reports:read"]`, while the effective dependency count stays at one. The declaration targets
therefore report two `matched` results. Caller-authored restricted policy intent remains one
`not-evaluated` result. The helper is explicitly a source-only placeholder, not an authentication
implementation; the example is never imported or executed. These are mock proposal/review artifacts,
not model output or a demonstration that access is denied or granted correctly.

## Read the three sections separately

- `preview` retains the exact diff, source/policy references, expected outcomes and draft/not-run status.
- `comparison` contains the existing source-only `matched`, `mismatched`, `unknown` or `not-evaluated`
  results. It compares supplied snapshots, not disk/Git freshness or runtime authorization.
- `regression_test_draft` is `structured-prose`, `status: draft`, `executable: false`, with
  `maintainer-authored-template` provenance. It describes purpose, references, planned observations,
  expected values and limitations; its observations remain null and verification remains not-run.

The draft is neither executable test code nor a shell/HTTP procedure. It does not copy declaration
comparison results into runtime observations or claim tests passed. Its bundle/request/review/proposal/
manifest/source identities and before/after hashes connect it to the supplied artifacts; the draft's
own identity changes with its bound content. None of these identities authenticates consent or grants
sharing, application, verification or restoration permission. Policy citations alone do not establish
policy correctness, and declared scopes alone do not establish enforcement.

Top-level `status: completed` and exit `0` mean composition finished, not that security or a test passed.
Application remains false, verification and runtime verification remain not-run, and authorization
remains unknown. Invalid arguments/options exit `2`; an internal failure, including invalid packaged
artifacts, exits `1`; interruption exits `130`. The command accepts no user artifact that could be
classified as an invalid input bundle.

## Python APIs and provenance

```python
from authzest.codex.review_demo import build_review_demo_bundle
from authzest.runner.review_demo import compose_review, run_review_demo

bundle = build_review_demo_bundle()
review = compose_review(bundle)
demo = run_review_demo()
```

`compose_review` also accepts an existing validated preview bundle, revalidates its contents and
returns detached data without reading embedded paths. It preserves supplied source-artifact identities
and provenance rather than labelling every input as mock. Its `live_provider_calls: 0` describes this
composition only, not historical provider usage recorded in the supplied artifacts. Draft template
provenance is separate from review/model provenance. Invalid artifacts raise `ContractError`.

`run_review_demo()` takes no arguments and identifies its fixed case as `scope-declaration-review`,
with caller-authored-mock artifacts and `simulated_draft: true`. Neither API calls a provider, applies a
proposal or executes a test. Generated executable regression tests, approved integration with a
broader repair workflow and the complete #35 acceptance remain separate work.
