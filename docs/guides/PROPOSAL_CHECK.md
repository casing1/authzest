<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/PROPOSAL_CHECK.md">한국어</a>
</p>

# Source-only proposal declaration checks

[Documentation index](../README.md) · [Proposal preview](PROPOSAL_PREVIEW.md) · [Expectation contract](../reference/EXPECTATION_CONTRACT.md)

## Scope and availability

[#69](https://github.com/casing1/authzest/issues/69) adds `authzest proposal-check` to the source
checkout after alpha.3. Use a source revision containing this change; the published alpha.3 binaries
do not contain this command. Package version `0.1.0a3`, scan report schema `1.2`, and the existing
proposal, expectation and preview-bundle schemas are unchanged. This is not a new release.

The command reads the same validated offline bundle as `proposal-preview`, then compares supported
declaration expectations with its baseline and proposed source strings. It does not import or execute
those strings, call Codex, start a worker, open paths embedded in the bundle, inspect Git or current
source files, apply a patch, or grant approval. These are supplied snapshots, not a check of disk
freshness, policy enforcement or runtime authorization. The fixed-fixture workflows are unchanged.

## Try the command

From the repository root with the [development environment](../../README.md#development-setup)
active, on a supported POSIX system:

```bash
preview_dir=$(mktemp -d)
python -m scripts.demo_preview --output "$preview_dir/bundle.json"
authzest proposal-check "$preview_dir/bundle.json"
authzest proposal-check "$preview_dir/bundle.json" --json
```

The existing exporter creates a caller-authored public-intent example. Its `policy-intent`
expectation is **`not-evaluated`**, not a matched authorization check. It makes no model call and
does not change the fixture. The exporter creates a new output file exclusively; the check command
itself is read-only. Both commands leave the selected bundle available for inspection.

For declaration comparisons, use the existing expectation/proposal APIs to package reviewed source
snapshots and explicit `dependency-declarations` or `scope-declarations` targets. For example,
`{"count": 1}` is a declaration-count target, and `{"scopes": ["items:read"]}` is a declared-scope
target. Their evidence references and hashes must be derived from the same request and exact
proposal, not manually copied from unrelated artifacts. A target's existence does not prove that
its cited policy supports it. See the [manifest API](../reference/EXPECTATION_CONTRACT.md#python-api-and-offline-checks).

## Initial supported subset

A structurally valid bundle can still be outside the comparison subset. Initially it must contain
exactly one selected source and one changed file. The baseline route evidence must fully match
re-parsing that source; a valid reference ID alone is insufficient. Both snapshots must use supported
module-level route registrations directly on a single `FastAPI` owner, without aliases or routers.
This is narrower than the ordinary `scan` parser's supported syntax.
Canonical `from fastapi import FastAPI, Depends, Security` names are supported, as are
`Annotated`/`Any` imports from `typing` or `typing_extensions`, supported primitive/generic/union
annotations, explicit dependency references and literal auxiliary arguments. Namespace imports,
custom imports/decorators and string/type aliases are not supported. Each source snapshot is limited
to 32,768 characters. Baseline analysis must be `bounded`, with no diagnostics or parse errors.

The checker does not guess through multiple files, aliases, router/include chains, dynamic or
conditional declarations, deferred registration, partial evidence, or ambiguous route correspondence.
Renamed/deleted routes and unsupported source return `unknown` for declaration comparisons, not a
successful or failed authorization verdict. Baseline registration IDs include source positions;
comparison does not assume that an ID stays unchanged after editing. Results retain source hashes,
evidence and registration identities so the selected before/after observations can be reviewed.
`before_observed` and `observed` hold the baseline and proposed declaration values; the latter is
compared with `expected`. Both observations and `after_registration_id` are `null` for `unknown`
or `not-evaluated` results. No baseline observation is presented as an after-edit measurement.

| Expectation               | Compared source observation                                        | Meaning and limits                                                                                                |
| ------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `dependency-declarations` | Number of effective dependency declarations                        | Ordinary `Depends` declarations count too; the count does not prove authentication or authorization.              |
| `scope-declarations`      | Sorted unique declared scopes on effective `Security` declarations | Declared scopes are not scope enforcement. Unresolved scope information is not silently treated as an empty set.  |
| `policy-intent`           | None; always `not-evaluated`                                       | Public/restricted intent is caller-authored policy interpretation, not something this checker infers from source. |

The source comparison reports `matched`, `mismatched` or `unknown` with the expected value,
before/after observations and reasons; policy intent reports `not-evaluated`. A mismatch is a
difference from the supplied declaration target, not a discovered vulnerability. Zero dependencies
or an empty scope set never classifies an endpoint as public, safe or vulnerable.

## Results, exits and input handling

`status: completed` and exit `0` mean that comparison processing finished, even when results contain
`mismatched`, `unknown` or `not-evaluated`. They are neither an all-matched summary nor a security
pass. Inspect the individual results. Runtime verification stays `not-run`, authorization stays
`unknown`, application stays `false`, and provider calls remain zero. Existing preview APIs still
return draft/not-run data; a comparison result does not become an approval receipt or executable plan.

The CLI uses the same bounded reader as [proposal preview](PROPOSAL_PREVIEW.md#file-handling-and-failures):
one stable regular UTF-8 JSON file, at most 256 KiB in total, with duplicate-key and nested contract
validation. A final-component symlink, special file, detected change, malformed input or inconsistent
artifact binding is rejected. Embedded source paths are never opened. Unsupported file-reader
platforms, including Windows, reject before opening the file; the pure in-memory API is cross-platform.
Parent-directory symlinks and hostile concurrent writes are not completely excluded, and the byte
limit is not a filesystem wall-clock deadline. Use a file and directory you control.

Invalid input exits `2`, an unexpected processing failure exits `1`, and interruption exits `130`.
Valid but unsupported source produces `unknown` results rather than becoming invalid JSON. No
provider, apply, execution or approval option is introduced. Local output can include selected source
or policy data; inspect it before publishing or redirecting it to shared logs.

## Python API

This example assumes an existing `request`, validated `review`, exact `proposal`, and reviewed
source/route/policy evidence IDs from that request. It supplies an explicit declaration target;
matching is conditional on the supported syntax and evidence checks above:

```python
from authzest.codex.expectations import prepare_expectation_manifest
from authzest.codex.preview import prepare_preview_bundle
from authzest.runner.proposal_check import check_proposal

manifest = prepare_expectation_manifest(
    request,
    review,
    proposal,
    expectations=[
        {
            "id": "one-declaration",
            "source_evidence_id": source_evidence_id,
            "route_evidence_id": route_evidence_id,
            "policy_evidence_ids": [policy_evidence_id],
            "observation": "dependency-declarations",
            "expected": {"count": 1},
            "limitations": ["Declaration count does not establish access control."],
        }
    ],
)
bundle = prepare_preview_bundle(request, review, proposal, manifest)
result = check_proposal(bundle)
```

`check_proposal` revalidates even a `ValidatedPreviewBundle` wrapper. The separate
`authzest.runner.proposal_check.load_check(Path("bundle.json"))` convenience API reads only the
explicitly selected file through the same bounded reader (with `Path` from `pathlib`).

The pure `check_proposal` path parses supplied strings as data and produces detached comparison
results. It does not read or write files, start processes, import the proposed application, or use
a provider. This bounded static comparison does not implement generated regression tests, general
repository repair, runtime authorization checking or the complete #35 workflow.
