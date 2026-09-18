<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/PROPOSAL_PREVIEW.md">한국어</a>
</p>

# Offline proposal and expectation preview

[Documentation index](../README.md) · [Expectation contract](../reference/EXPECTATION_CONTRACT.md)

## Scope and version

[#63](https://github.com/casing1/authzest/issues/63) adds `authzest proposal-preview` after alpha.3.
Use an editable source checkout containing this change; the published alpha.3 binaries do not contain
this command. Package version `0.1.0a3`, report schema `1.2`, and existing proposal/expectation schemas
are unchanged. This is a presentation step under #35, not completion of its approval or execution workflow.

The command reads one explicitly selected JSON bundle and revalidates its request, review, proposal and
expectation manifest before displaying their linked evidence, exact diff, rationale, expected outcomes
and limitations. It does not read paths named inside the bundle, inspect Git or current source files,
call Codex, approve or apply a patch, or generate or execute tests. Existing `codex-fixture` artifacts
are not this input format, and its live input-sharing and execution boundaries are unchanged.
The separate [source-only `proposal-check`](PROPOSAL_CHECK.md) command can compare declaration
targets with supported source snapshots from the same bundle. It does not change this preview's
draft/not-run status, evaluate policy intent or grant approval or execution.

## Reproducible offline demo

From the repository root, with the [development environment](../../README.md#development-setup) active,
on a supported POSIX system:

```bash
preview_dir=$(mktemp -d)
python -m scripts.demo_preview --output "$preview_dir/bundle.json"
authzest proposal-preview "$preview_dir/bundle.json"
authzest proposal-preview "$preview_dir/bundle.json" --json
```

The exporter reads only the existing public-intent development fixture
`tests/fixtures/ai_evaluation/v1/public/main.py` and inventories it without importing application code.
It combines a caller-authored policy, a scripted `unknown` review, a harmless comment-only proposal and
a public-intent expectation. This is neither a live model result nor a security fix. The frozen corpus
and held-out cases remain unchanged.

`--output` creates a new file exclusively and refuses to overwrite an existing path. Without it, the
exporter writes the bundle to stdout. This exporter writes only the explicitly selected output; the
product preview command itself is read-only. The temporary directory remains available for inspection.

The default view groups the supplied evidence and expected outcomes with the derived diff and
limitations. `--json` returns the validated preview as ASCII-escaped JSON. Untrusted display strings
are escaped rather than treated as terminal control sequences. Output remains local but can contain
source text and policies from the selected bundle; review it before sharing or redirecting it to logs.

## Bundle format and Python API

Bundle schema `1.0` accepts exactly `schema_version`, `request`, `review`, `proposal`, and `manifest`.
The last four fields are nested JSON objects from the existing contracts, not filenames or separately
encoded JSON strings. The entire serialized bundle is limited to 256 KiB of UTF-8. Existing strict JSON
limits, duplicate-key rejection and nested contract checks also apply; individually valid artifacts
can still exceed the combined limit.

If those four artifacts already exist in memory:

```python
from authzest.codex.preview import (
    prepare_preview_bundle,
    preview_bundle,
    validate_preview_bundle,
)

bundle = prepare_preview_bundle(request, review, proposal, manifest)
validated = validate_preview_bundle(bundle.payload_json)
preview = preview_bundle(validated)
```

The immutable `ValidatedPreviewBundle` stores canonical JSON and exposes a content-bound `bundle_id`.
Returned dictionaries are detached; preview consumers revalidate the bundle rather than trusting the
wrapper alone. Changing material artifact content changes its identity or makes its bindings invalid.
The pure APIs are platform-independent and perform no filesystem, process, provider or network I/O.

The preview retains request metadata, review content, evidence and proposal/manifest identities.
Its fixed status is `draft`, verification is `not-run`, application is `false`, observations are `null`,
and authorization remains `unknown`. These are structural checks of supplied snapshots, not proof of
policy approval, semantic correctness, current disk/Git freshness, or a successful security repair.
Policy intent is caller interpretation; ordinary DI and scope declarations do not establish enforcement.
No approval record binds this bundle or grants it execution authority.

## File handling and failures

The CLI file reader initially supports POSIX systems with `O_NOFOLLOW` and `O_NONBLOCK`; unsupported
systems, including Windows, fail before opening the input. This restriction does not affect scanning
or the pure Python APIs.

The selected input must be a regular UTF-8 file within the size limit. A final-component symlink,
FIFO or other special file, a detected change during reading, invalid UTF-8, malformed JSON or
inconsistent artifact binding produces exit code `2`, an error on stderr and no partial preview on
stdout. The reader does not promise to reject symlinks in parent directories or provide a snapshot
guarantee against a hostile concurrent writer. Use a file and directory you control.
The byte bound is not a wall-clock timeout for filesystem access.

Successful validation exits `0`; it does not mean an expectation passed. No approval, apply, execution
or provider option is added. Later approval and verification integration requires its own exact plan
and separately reviewed boundaries.

## Offline checks

```bash
python -m pytest tests/test_preview_bundle.py tests/test_proposal_preview_cli.py
```

These tests cover the bundle contract, linked presentation and rejected file/input cases without
calling a live provider or executing the proposed application source. They are not model-quality,
runtime-authorization or published-binary acceptance results. No release is implied by this source addition.
