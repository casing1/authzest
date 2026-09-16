<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/FIXTURE_DEMO.md">한국어</a>
</p>

# Offline fixture walkthrough

[Documentation index](../README.md) · [Copy application boundaries](FIXTURE_APPLICATION.md)

## Scope and availability

[#65](https://github.com/casing1/authzest/issues/65) adds `authzest fixture-demo` after alpha.3.
Install a source revision containing this change; published alpha.3 binaries do not contain it.
The command uses a packaged, maintained fixture and a caller-authored mock review and proposal.
It needs neither the repository's `scripts/` and `tests/` directories nor a Codex installation,
account or network connection. It is not a live AI result or a new release.

The sole proposed change is the fixed `debug=True` → `debug=False` replacement in a fresh private
fixture copy. Existing checkouts and original fixture files are not modified. The command initially
requires supported POSIX file operations; unsupported systems, including Windows, reject the workflow
before creating files. Existing Windows scan support is unchanged.

## Run the walkthrough

With the current source installation on PATH, run from any working directory:

```bash
authzest fixture-demo --help
authzest fixture-demo
```

For a locally built executable containing this change, use its exact path instead of `authzest`.
The command accepts no target path, bundle, model, runtime selector or automatic-approval option.
Only `--help` is available. Read the displayed evidence, exact diff, identifiers and limits before
answering each prompt; placeholder identifiers below are not literal values to enter.

1. Type the exact displayed `apply <proposal-id>` to apply that proposal to the new copy.
2. After application, inspect the fixed source-configuration plan. Type `verify <plan-id>` to
   approve that separate check. Applying a patch does not approve verification.
3. Inspect the restoration preview. Type `restore <proposal-id>` to restore the copy, separately
   from the application and verification decisions.

Enter or other nonmatching text declines the current step; `cancel`, EOF or interruption at a prompt
cancels that step. Declining application stops before checks or restoration. Declining verification
leaves it `not-run` and still offers restoration. Declining restoration keeps the applied copy.
A failed check is not a successful fix; restoration remains a separate decision after check failure.

## What runs and what remains

Only the separately approved, fixed AST/source-configuration worker runs in a child process. It reads
the exact maintained fixture bytes as data to inspect the debug declaration; it never imports or
executes fixture source. Its preview identifies the fixed checker, source hashes and limits. No model,
generated test, arbitrary command, install hook or runtime fixture check runs in this command.
A separate process and reduced environment are not an OS or network sandbox.

The fresh workspace, before/after snapshots and local record are retained for inspection, including
after decline or failure if they were created. Restoration refuses detected later edits rather than
overwriting them. Do not concurrently edit the copy during an operation. Inspect the displayed
workspace after an interrupted or uncertain operation; the journal is not crash recovery or a
restart/resume capability, and temporary storage is not a permanent backup.

Mock provenance, zero live provider calls and runtime verification `not-run` must not be confused
with live-model quality, authenticated human consent, authorization correctness or a verified
security repair. This workflow reuses the existing copy and fixed-check boundaries; broader #35,
general repository changes and generated regression-test support remain unfinished.

The read-only [#63 proposal bundle](PROPOSAL_PREVIEW.md) is not an executor input here.
The [expectation manifest](../reference/EXPECTATION_CONTRACT.md) describes policy/declaration targets,
not this debug setting, and is not treated as approval for this walkthrough.
The development-only `python -m scripts.demo_verify --runtime-check` remains a separate opt-in
[runtime demonstration](RUNTIME_VERIFICATION.md); `fixture-demo` does not expose that option.
