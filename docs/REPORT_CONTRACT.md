<p align="center">
  <strong>English</strong> ·
  <a href="i18n/REPORT_CONTRACT.ko.md">한국어</a>
</p>

# Source report contract

[Documentation index](README.md) · [Parser scope](PARSER_SCOPE.md) · [Example](EXAMPLES.md)

This describes schema **1.0** in the current source, not the published alpha binary. The report schema
version is independent of the package version, which remains 0.1.0a1. The core, CLI JSON, and local API
serialize the same report. No dependency classification, AI proposal, source modification, or target
execution is performed by this report implementation.

## Compatibility and fields

The first versioned schema extends the earlier unversioned inventory. Existing fields and their meanings
remain; consumers that reject additional keys must accept the new fields before upgrading. Treat a
missing schema version as the legacy format, not automatically as 1.0. Future additive fields may be
introduced in a minor schema version; removal, renaming, or changed meaning requires a major version and
documented migration. Consumers should tolerate unknown keys but reject unsupported major versions.

| Field                   | Meaning                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------- |
| `schema_version`        | String identifying the report contract; currently `1.0`                                |
| `root`                  | Absolute selected scan root; local machine context, not part of registration identity  |
| `python_files`          | Number of selected Python files, including files that could not be parsed              |
| `route_count`, `routes` | Number and ordered list of discovered source registrations/declarations                |
| `parse_errors`          | Preserved legacy error strings; may include absolute paths and platform-dependent text |
| `codex_status`          | `disabled` in the current scan; no AI call is made                                     |
| `analysis_status`       | `partial` if any diagnostic or legacy parse error exists; otherwise `bounded`          |
| `diagnostics`           | Ordered structured source/read/unsupported-pattern diagnostics                         |

Neither status means complete runtime coverage, a vulnerability finding, or an access-control guarantee.
`bounded` means no diagnostic was collected within the supported subset, not that every unsupported
construct was recognized. Empty source directories may produce a bounded, zero-route report. Some
unknown imports, receiver aliases, middleware, or dynamic code remain silent; see the parser scope.

## Registration evidence

Each route keeps its original `path`, `methods`, `function`, `file`, and `line`. The legacy line identifies
the function definition; it is not the decorator or mount line. Two additional fields are:

- `registration_id`: opaque `route-` plus a SHA-256 hexadecimal digest.
- `registration`: original declaration and owner, application context when known, include chain, and scope.

The parser fills both fields for its emitted routes. A manually constructed legacy core `Route` without
provenance serializes both as null; consumers must not manufacture verified ownership for it.

| Registration member | Meaning                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------- |
| `declaration`       | Source location of the decorator call expression (after the `@`)                                              |
| `owner`             | Original route owner's `kind` and constructor `location`                                                      |
| `application`       | Source FastAPI owner receiving the composed route, or null for a standalone router                            |
| `include_chain`     | Outermost-to-innermost registrations; each has call `location`, `parent`, `router`, and literal call `prefix` |
| `execution_scope`   | `module` or `deferred`; deferred function-body inventory does not prove invocation                            |

Locations have `file`, `line`, and `column`. New evidence/diagnostic file paths inside the root use relative
POSIX separators. The old route `file` field retains native OS separators for compatibility. Lines and
columns are one-based; columns count UTF-8 bytes, not editor display cells or Unicode characters. Unknown
error coordinates are null. Owner locations identify constructor calls, not variable assignment targets.

Repeated identical paths are distinguished by their exact decorator, owner/application, and include-site
positions, including separate calls on the same line. A nested chain records every supported source
registration; it does not claim that the source has been imported or any endpoint deployed.

The digest is computed from canonical JSON containing route path, methods, function, POSIX-relative file,
function line, and the full registration object. JSON keys are sorted, separators are compact, Unicode is
retained, and UTF-8 bytes are hashed. Identical inputs produce identical IDs across repeated scans and
relocation of the selected root. Route order follows deterministic source discovery/import composition,
not alphabetical endpoint order. Diagnostic wording can differ across Python/OS versions.

**An ID is not a source-content hash, persistent runtime identity, or approval token.** A function body
can change without moving its declaration. Future patch approval must separately bind the exact diff and
original content/revision, reject stale approvals, and preserve user changes. See [workflow #35](https://github.com/casing1/authzest/issues/35).

## Diagnostics

Each diagnostic contains `code`, `message`, `severity`, and `location`. Severity is source-processing
`error` or `warning`, not vulnerability severity. File read/parse/decode failures are errors; known
unsupported declarations are warnings. Either makes the analysis partial. Legacy parse errors are retained
alongside their structured counterpart; do not add the two lists together as independent failures.

The supported reason codes and trigger boundaries are listed in the [parser scope](PARSER_SCOPE.md).
In particular, an unresolved include child is diagnosed at an evidenced include attempt; this is not an
exhaustive inventory of unresolved imports. Source parse errors retain valid routes from other files.
The JSON diagnostic record is structured output, not an HTML-safe string or a command to execute.

## CLI and API behavior

Run from the source checkout after installation:

```bash
authzest scan examples/fastapi_inventory
authzest scan examples/fastapi_inventory --json
authzest scan examples/fastapi_inventory --json --strict
```

| Situation                                     | Default CLI             | CLI with `--strict`     | Local scan API                                  |
| --------------------------------------------- | ----------------------- | ----------------------- | ----------------------------------------------- |
| Valid root, bounded inventory                 | Exit 0, report          | Exit 0, report          | HTTP 200, report                                |
| Valid root, known partial inventory           | Exit 0, report          | Exit 1, report          | HTTP 200, report                                |
| Missing root or a file instead of a directory | Exit 2, error on stderr | Exit 2, error on stderr | HTTP 400 if the configured workspace disappears |

Strict mode is opt-in so existing scripts retain their default exit behavior. It fails on known analysis
limitations, not security findings. JSON mode emits the full report on stdout before strict mode exits 1,
without mixing diagnostic text into stderr. Human output includes source paths, registration IDs,
application/include positions, scope, and diagnostic details. Text layout is intended for people; use the
versioned JSON contract for integrations. Unexpected internal exceptions are not security verdicts.

The API remains bound to the workspace chosen at server startup; callers cannot select a different path.
There is no API strict flag: consumers must inspect `analysis_status` and `diagnostics`. The dashboard
distinguishes partial/bounded inventory, uses registration IDs as row keys, and preserves legacy errors
in a separate expandable list.

## Regression evidence

[Model contract tests](../tests/test_report_contract.py) cover canonical identity, root relocation, null
legacy provenance, and field/status compatibility. [Parser tests](../tests/test_report_parser.py) cover
source positions, same-line repeated mounts, multiple apps, nested cross-file composition, known unresolved
cases, deferred scope, and read-once source-only processing. [Transport tests](../tests/test_report_transports.py)
cover CLI/API equivalence, output before strict failure, and invalid/empty/partial inputs.
