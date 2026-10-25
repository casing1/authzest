# Historical evaluation inventory

[Documentation](../README.md) · English · [한국어](../i18n/ko/development/EVALUATION_INVENTORY.md)

This source-checkout development tool tracks existing evaluation-related artifacts for
[#108](https://github.com/casing1/authzest/issues/108), a preparatory slice of
[#84](https://github.com/casing1/authzest/issues/84). It detects missing or changed file bytes without
running the artifacts. It does not select or freeze a new benchmark, approve reference labels, compare
models, or complete #84. It is not a packaged `authzest` command or a published alpha.3 feature.

## Run the inventory check

From the repository root with Python 3.12 or later:

```bash
python scripts/check_evaluation_inventory.py
python scripts/check_evaluation_inventory.py --json
```

The default output is a concise human-readable integrity summary. `--json` emits a machine-readable
result. Neither form calls a provider, uses the network, imports fixture/policy source, executes a
target or policy, runs an evaluation, changes files, applies patches, or grants any approval.

| Exit | Meaning                                                                                       |
| ---- | --------------------------------------------------------------------------------------------- |
| `0`  | The manifest schema and listed artifacts' byte hashes match.                                  |
| `1`  | Invalid manifest/path, missing artifact, read failure, resource limit, or byte-hash mismatch. |
| `2`  | Invalid command-line usage.                                                                   |

Exit `0` is not a passing benchmark, correct label, completed review, permission to execute, or security
guarantee. The checker does not establish whether manifest declarations accurately describe the files.

## Keep the historical groups separate

The [manifest](../../tests/fixtures/evaluation_inventory.json) records repository-relative artifact
paths, SHA-256 hashes of raw file bytes, and declared historical context. These groups have different
purposes and review histories; do not sum them into a single benchmark denominator.

| Historical group               | Declared context                                                                                                                                                                             | Boundary for new #84 evaluation                                                                                                                                         |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #33 declaration/mock corpus    | Six source cases, ten questions; three development cases and three historical declared held-out cases. Assistant-authored labels have approved policy criteria and code-checked values.      | Not independently benchmark-reviewed. Preserve the existing split and corpus identity; historical held-out names do not establish secret or newly independent holdouts. |
| Owner-policy developer cases   | 28 assistant-authored expected labels; policy criteria approved, exact-label review pending.                                                                                                 | Developer regressions, not approved benchmark labels.                                                                                                                   |
| #77 owner-case review          | Original proposed record plus separate maintainer review of ten model-authored cases. Exact labels were approved through a recorded chat decision; the reviewer record is not authenticated. | Preserve authorship and the original pending/draft record. The later exact review is not blanket approval of other labels or a new independent benchmark.               |
| #80 policy observations        | Two historical observations of the same ten reviewed cases under separate recipe versions.                                                                                                   | Not 20 unique cases, a new execution, or attestation of current code. The historical one-run approvals are consumed.                                                    |
| Reviewed synthetic repair pair | Eight assistant-authored synthetic developer labels with recorded exact review; the source module embeds the pair and review context.                                                        | No execution observation is added. Label/source review does not approve execution, patch application, or new benchmark use.                                             |

Every group is reference-only for the new #84 evaluation, with candidate selection `not-selected` and
independent benchmark review `not-established`. These new-evaluation states do not revoke historical
label approvals or change #33's existing historical split. Source-context files support interpretation;
they are not additional cases or independently reviewed labels.

Existing canonical corpus, case, review, source, and plan identities remain unchanged. A SHA-256 hash
of a whole file's bytes is a different identity from a canonicalized JSON object or a multi-file corpus
digest. Do not substitute one for another. Existing semantic/provenance regression tests separately
check their historical bindings; this inventory checker verifies only schema, paths, and bytes.

## Validation and limits

The checker uses a strict manifest schema and rejects unsafe repository-relative paths, symbolic links,
non-regular files, missing files, and mismatched SHA-256 hashes. Reads are bounded: at most 256 KiB for
the manifest, 4 MiB per artifact, and 64 artifact files in total. It reads source as data rather than
importing or executing it.

The repository pins LF checkout line endings for the inventoried text paths through `.gitattributes`.
The checker performs no newline normalization; changing those bytes to CRLF still reports drift.

Hash agreement is not authenticity. Someone changing both the manifest and an artifact can make them
agree. The manifest's counts, authorship, review statements, selection status, and other historical
descriptions remain declarations, not machine-attested facts. The checker cannot establish independent
review, label correctness, consent, current implementation behavior, model quality, or security.
It is not a hostile concurrent-filesystem sandbox; use a stable checkout with a trusted toolchain.

When an artifact intentionally changes, review its provenance and affected semantic tests before
updating its inventory hash. Do not mechanically refresh hashes to silence drift. Preserve historical
records and approvals; record a genuinely new artifact separately when it represents a new observation
or review. Re-run the checker and applicable tests in the same focused PR.

## What remains under #84

Follow the [model strategy](MODEL_STRATEGY.md) for independent exact reference-label review, maintained
task selection, new holdouts, comparable inputs and denominators, abstention handling, and eventual
three-mode evaluation. Selecting or freezing that evaluation set requires a separate documented
decision. This inventory supplies neither performance measurements nor a model-quality conclusion.
Any live model call, source sharing, policy execution, or patch application still needs its own scoped
decision; the inventory check does not consume or renew an earlier approval.
