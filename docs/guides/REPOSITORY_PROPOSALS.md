# Proposals for an external FastAPI folder

[Documentation](../README.md) · English · [한국어](../i18n/ko/guides/REPOSITORY_PROPOSALS.md)

This unreleased source feature reads files you explicitly select from an external project and can
request a new PoC and one-file repair proposal through Codex. The unchanged default proposes Python
regression-test text; the explicit `--http-poc` mode proposes bounded HTTP request data instead.
Neither substitutes the packaged demonstration source for your selection. Stable publication remains
on hold while external-project support is completed; see the
[frozen 0.1.0 scope](../development/0.1.0-SCOPE.md).

This is a **proposal-only CLI stage**. It does not run the target or generated test, contact the
target over HTTP, create a copy, apply a patch or restore files. The current GUI's active workflow
still uses the packaged owner-read scenario. Its workspace setting selects only the static scan root.
The new repository result JSON is not yet supported by the GUI's saved-result importer.

## Opt in to the HTTP-data proposal

Use `--http-poc` for the limited external GET object-ownership proposal. Start with an offline
preview, replacing the root, source, policy and model placeholders with your reviewed values:

```bash
authzest repo-suggest /path/to/project --source app.py --policy policy.md --model EXPLICIT_MODEL --http-poc --preview-only --json
```

This example previews input only; it does not call Codex, send an HTTP request or run the app.
The HTTP mode requires a self-contained **single flat ASCII-identifier `.py` source file** with a
supported GET declaration, not a package, nested Python path or `__init__.py`. The source limit is
**16 KiB**, the policy limit is **8 KiB**, and `--context` is refused in this mode. `--app-attribute`
is optional, defaults to `app`, and is available only with `--http-poc`. Its plain app-attribute and
module names, import root `.`, lifespan off and no authentication overrides are bound declarations,
not proof that an importable app or representative identity setup exists.

The new request is built directly from the captured inputs as schema **2.0**, kind
`repository-http-proposal-request`; it is not a conversion of a saved v1.0/v1.1 request. The complete
source, policy, selected interface, partial static evidence, model, instructions, prompt and output
schema bind its request identity. The sharing-preview wrapper is
`repository-http-sharing-preview`, also schema 2.0. Independent expected case answers are not
provided to the model, and the policy remains unverified user-provided intent.

A `proposed-change` response contains newly authored replacement source (`after_text`) and one PoC
data object with `method`, `path` and `headers`. The method is `GET`; the path is a bounded literal
relative path without query strings, traversal or an absolute URL. `headers` is an array of zero to
three unique `{name, value}` records: names are limited to `x-user`, `x-user-id` and `x-role`, and values
use the bounded synthetic `test-*` grammar. Expected responses, assertions, Python/pytest, commands
and credentials are not PoC fields. Synthetic identity and anonymous-policy checks do not establish
the safety of a real authentication system.

To request a proposal, retain `--http-poc` and remove `--preview-only`; the current sharing and
recapture controls below still apply. At most one adapter call follows a fresh exact sharing decision,
with no application retry or model fallback. The final result kind is `repository-http-suggestion`,
schema 2.0; its response kind is `repository-http-proposal`. The host derives one source-only diff,
binds the complete response and hashes the PoC data. There is no generated-test path or fabricated
T/pytest result. Execution, copy creation, patch/original application and restoration remain not-run;
authorization is unknown and `verified_fix` is false. No-change, unknown and refused remain valid
proposal outcomes.

The new request and named `suggest_repository_http` adapter entry have offline/scripted validation,
not an actual provider acceptance run for the pinned Codex 0.153.0 and schema 2.0. Future isolated
A/B execution, independent cases, original correction and GUI import still require their own
integration. The saved-result GUI is a release goal for this mode, not a delivered importer.

## Prepare the selected inputs

Use the updated non-frozen source installation on POSIX and activate its Python environment. The
dashboard/frontend build and Docker runtime are not required for this proposal-only CLI command.
The package requires Typer **0.27.3 or newer**; older environments must resolve the updated
package dependencies before using the CLI. The former 0.9 lower bound could not parse its union
annotations, so the minimum-version CI now checks both root and proposal help.
The existing Codex adapter requires a trusted Codex CLI **0.153.0**, an existing ChatGPT login and an
explicit accessible model identifier. Offline preview does not contact Codex or use an account.

Select paths relative to the external project root:

| Input   | Requirement                                                                                                |
| ------- | ---------------------------------------------------------------------------------------------------------- |
| Source  | One editable Python file, selected with `--source`                                                         |
| Policy  | One nonblank UTF-8 `.md` or `.txt` document selected with `--policy`; describes your intended access rules |
| Context | Default mode only: up to four other Python files via `--context`; read-only, not extra repair targets      |

The policy is user-supplied intent, not inferred or verified runtime truth. Explain which actors may
access which resources, expected denial/public behavior and any test setup or missing fixture assumptions.
In the default mode, include the relevant authentication/ownership helper as context when it lives in another file.
The HTTP mode is limited to the single self-contained source and refuses context files.
Dependencies and unrelated files are not automatically discovered, read or imported.

Paths must be explicit relative POSIX paths without absolute paths, hidden components, empty/dot/
parent components, backslashes or control characters. Symlinks, hardlinks, directories and special
files such as FIFOs are refused. The root and its parents must also be reached without symlinks;
use a canonical path, such as `/private/tmp` rather than the macOS `/tmp` alias.

Each Python file is limited to **16 KiB**, the policy to **8 KiB**, and all selected bytes together to
**64 KiB**. Input must be UTF-8 without NUL bytes. Empty Python context files are allowed. The loader
holds descriptors and rechecks bytes, names and metadata to detect ordinary edits/replacements; it
does not promise an atomic snapshot against a hostile concurrent writer.

Selected-source parsing also stops at **64 registration additions and 64 diagnostics per file**.
Registration work includes intermediate router copies, not only the final visible routes. Combined
route/diagnostic evidence is limited to 64 each. Complex compositions can therefore be refused even
when their final inventory would be small; this proposal path does not expand unbounded router graphs.

## Preview before sharing

Replace the root, selected paths and `EXPLICIT_MODEL` with your reviewed values. The following
example selects only the source and policy:

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --model EXPLICIT_MODEL --preview-only
```

Add explicitly selected context when needed. Repeat the context option for additional files:

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --context auth.py --model EXPLICIT_MODEL --preview-only --json
```

Preview shows the complete selected source/context/policy, source hashes, static declarations,
diagnostics and limitations, prompt, response schema and request limits. The parser consumes the
captured Python bytes; it does not reopen or import the target. Selected-file evidence does not
resolve a whole application's import/dependency graph or prove runtime authorization. Missing context
can legitimately lead to unknown or refusal.

The local absolute root is excluded from the provider payload. Selected text can itself contain paths
or secrets: explicit selection is not secret detection. Review the complete request before sharing it.

## Request one proposal

Remove the preview flag to enter the interactive sharing step:

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --context auth.py --model EXPLICIT_MODEL
```

Review the full current preview, then type the exact displayed sharing phrase. Enter declines;
cancel cancels. The decision expires after **300 seconds** and is bound to this invocation. The
workflow recaptures every selected file before sending; changed or unavailable inputs stop the
request. A previous phrase, saved JSON or edited request does not approve a new invocation.

At most one local adapter call is made, with a finite adapter timeout up to **120 seconds** and
separate cleanup time. There is no application retry or model fallback. Codex's internal transport
retries and actual token/cost usage are not separately hard-capped; existing account usage can be
consumed. The adapter uses the existing ChatGPT login and adds its harness context. Its trusted
transport runs with the existing empty-working-directory/tool-restriction controls, not your target
as an agent workspace.

## Read and retain the result

Without `--http-poc`, the final kind remains `repository-suggestion`. The proposal status is `proposed-change`, `no-change`,
`unknown` or `refused`; transport/input/expiry failures remain separate workflow states. A proposed
change contains a complete replacement for the selected source and a new proposed pytest regression.
The host binds the response to the request and before hash, checks bounded Python AST shape and
derives exact diffs. These checks establish neither safe execution nor policy correctness, exploit
reproduction, test collection or a verified fix.

The proposed test path is `tests/test_authzest_regression.py`. It is an output label only: this stage
does not read that path, check that it is absent or create/overwrite it. Context files are not editable
proposal targets. Inspect rationale, assumptions, uncertainties and limitations as well as both code
artifacts and the host-derived diff. Execution, application and restoration remain not-run.

For a single final JSON on stdout, use the JSON option and save the output in a reviewed private
location. Complete sharing preview and prompts are sent to stderr, so review them before deciding.

```bash
authzest repo-suggest /absolute/external/project --source app.py --policy policy.md --context auth.py --model EXPLICIT_MODEL --json
```

The JSON includes selected source/policy and generated code; treat it as private source material.
Do not import it into the current GUI expecting the owner-read apply/check/restore flow. External
private-copy staging, approved application, isolated before/after execution, restoration and GUI
integration remain follow-up work.
The [external file-workflow design](../development/REPOSITORY_FILE_WORKFLOW.md) defines the next
steps. Its S1 Python API prepares only metadata; it does not enable those operations or final writes
to the original project.
The separate [S2 Python file-session API](../reference/REPOSITORY_FILE_SESSION.md) now implements
owned private file transitions with offline tests. This command does not invoke it; external runtime,
operator and GUI integration remain pending.
The [S3 v1.1 interface/case comparison contract](../reference/REPOSITORY_VERIFICATION.md) is also a
separate pure API. The command's default remains v1.0; the explicit HTTP mode uses the distinct 2.0
request, not that v1.1 test interface. Supplied comparison data cannot enable writes or establish
actual execution.
The [runtime foundation](../reference/REPOSITORY_RUNTIME.md) adds a separate internal checkpoint,
sealed inputs and fake-tested guest/HTTP source. Its static create plans and unbuilt recipes do not
activate this command's execution or file workflow.

## Verification boundary

This implementation is checked using owned temporary inputs, offline/mock adapters and trusted fake
protocol peers. No actual provider call or private user repository sharing is established by those
tests. The packaged owner-read observations and earlier release-candidate checks remain tied to
their recorded source/scope; they are not an external-project end-to-end acceptance result.

The [official App Server turn documentation](https://learn.chatgpt.com/docs/app-server#turns)
describes per-turn `outputSchema`. It does not establish actual schema-2.0 compatibility with the
pinned local Codex version or successful model generation in this delivery.
