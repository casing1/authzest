<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/CODEX_OWNER_REVIEW.md">한국어</a>
</p>

# Read-only Codex review of the owned report policy

[Documentation index](../README.md) · [Owner policy](OWNER_POLICY.md) · [Codex configuration fixture](CODEX_FIXTURE.md)

## Scope and availability

[#75](https://github.com/casing1/authzest/issues/75) adds `codex-owner-review` to the current source.
It connects one maintained report-access example to an opt-in, read-only Codex review and structured
defensive test-case drafts. It is not in the published alpha.3 binaries. Package version `0.1.0a3`,
scan report schema `1.2`, released assets and the separate `codex-fixture` workflow are unchanged.

This slice has no generated code, diff, patch application, HTTP endpoint tests or execution of the example
application, endpoint or policy function. A valid result may retain unknowns or say no supported
change is needed; it never has to invent a patch. General repository review and the broader
[#35 workflow](https://github.com/casing1/authzest/issues/35) remain unfinished.
Offline tests and previews are not a live-model acceptance result. One separately approved live
attempt failed on 2026-09-24 without an accepted draft; live-model acceptance remains pending.
The attempt and its limits are recorded below. Another provider attempt requires fresh approval.

## Preview before sharing

Use a source installation containing this change. `MODEL` is a placeholder: replace it with the exact
model ID you intend to request. No model is selected automatically. From any supported OS:

```bash
authzest codex-owner-review --model MODEL --preview-only
```

This prints one complete JSON preview and exits without prompting, launching Codex, accessing an
account or making a network request. It requires neither Codex nor a login. There is no `--json`,
arbitrary path or automatic-approval option. The preview includes the request, task prompt, host
instructions, output schema and limits, along with the `sharing_id` to which approval is bound.
This ID covers that entire sharing envelope, not just the request ID. Codex adds its own harness
context, so the preview is not a claim to show the model's entire context.

The task/source input is limited to:

- Packaged, maintained snapshots of `examples/fastapi_owner_policy/main.py` and `policy.py`, with
  source identities and line references. These are embedded snapshots, not reads of your checkout.
- The explicit owner-only report policy and its trust assumptions.
- Static route and `Security` declaration evidence derived without importing or executing source.

The 28-case developer matrix, its expected labels and the frozen evaluation corpus are not model
inputs. Tests check that packaged snapshots match the maintained example; the command does not
claim to check whether your local example has changed. No other repository files, user-selected
paths or credentials are added to the task/source payload.

## Explicit, bounded account use

On supported POSIX systems, use a trusted Codex **0.153.0** installation with an existing ChatGPT
login managed by Codex. This is a compatibility pin, not a claim that the installed or newest Codex
version is compatible. The command does not install Codex, log in or read credential files itself.

```bash
authzest codex-owner-review --model MODEL --timeout-seconds 120
```

The timeout defaults to 120 seconds and cannot exceed 120. The command first displays the full JSON
preview. Only typing the displayed `share <sharing_id>` phrase exactly permits the provider path.
Enter, another answer or prompt cancellation shares nothing and starts no provider process. Preview
and decline work on all supported OSes; the actual provider path is POSIX-only. Successful login,
policy-criteria approval and permission to implement this feature are not source-sharing consent.

After consent, the shared pinned App Server transport allows at most one application-issued turn,
with no AuthZest retry, model fallback or model substitution. Codex internal communication retries
may still consume usage. The timeout and application-attempt count do not guarantee a token or
monetary cap; absent usage remains unknown. The transport reuses the effective configuration,
identity, tool/context and protocol checks described in the [configuration-fixture guide](CODEX_FIXTURE.md).
It starts in an empty working directory, accepts only the built-in OpenAI provider with ChatGPT
authentication, checks the requested/negotiated model and rejects tool work. No source execution,
shell command, repository exploration or HTTP test is part of the requested review. A trusted local
Codex installation remains an assumption, not an executable sandbox guarantee.

The official [App Server documentation](https://learn.chatgpt.com/docs/app-server) describes the
underlying interface. AuthZest's exact sharing envelope, version pin and read-only result contract
are narrower application rules, not general Codex limitations.

## Live attempt on 2026-09-24

The source CLI at commit `c5be74d6e65c7716ab3eff12ce2f0169fd889b2f` was tried once with Codex
`0.153.0`, the existing managed ChatGPT login and the exact requested model `gpt-6-astra`.
The user separately approved the two public source snapshots, policy and static evidence, at most
one application-issued turn and 120 seconds. Under that approval, the assistant compared the full
sharing envelope and entered the exact sharing phrase. This was not independent human review of
model-authored case expectations.

The CLI returned `review-failed`, exit `1`, after `98828.2639` ms (about 98.8 seconds), with no
accepted draft. Returned model identity, usage, warning count and retry count were `null`/unknown.
The detailed failure stage and cause were intentionally redacted, so this result does not establish
a timeout, authentication or quota failure. `application_turn_attempts=1` records the local attempt;
it does not establish how many turns the server accepted or the amount of account usage.

No further provider attempt was made. No target, application, policy-function or generated-code
execution, HTTP testing or patch application occurred. The feature worktree and original `main` checkout were
clean after the run, and both maintained example source hashes were unchanged. Execution remains
`not-run`, authorization remains `unknown`, and the independent developer labels remain unreviewed.
This failed attempt does not complete live acceptance, broader #35 or a release.

The one-attempt approval is consumed. The proposed next work, not yet begun, is a safe redacted
failure-stage diagnostic design with offline tests, followed by a new live attempt only after fresh
source-sharing and account-usage approval. No automatic retry is authorized by the failed result.

## Interpret the result

Interactive mode prints the preview, asks for consent and then prints a final JSON result. Its whole
terminal output is not one JSON document; use `--preview-only` for a single preview document.

A validated draft contains evidence-linked review answers and 1–16 structured defensive cases.
Each case describes principal/report inputs, an expected boolean and a reason; these are data for
review, not executable test code. The host validates the schema, request/source identities and
allowed evidence references. It does not prove that the model's explanation or expected value is
correct. Results remain `draft`, case expectations remain model-authored and unreviewed,
`execution_status` remains `not-run`, and `authorization_status` remains `unknown`.

The maintainer approved the policy criteria on 2026-09-24: authenticated identity, exact
`reports:read` scope and matching ownership are all required, with no admin exception and denial
when information is missing. This does not independently approve the 28 assistant-authored
developer labels or future model-authored cases. The example still has deliberately unconfigured,
fail-closed authentication. A source-linked review does not turn it into real authentication or
demonstrate endpoint authorization.

| Outcome                                            | Exit  | Meaning                                                |
| -------------------------------------------------- | ----- | ------------------------------------------------------ |
| Preview or `draft-ready`                           | `0`   | Preview/result handling completed, not a security pass |
| Decline, EOF or cancellation at the sharing prompt | `0`   | `not-shared`; no provider process                      |
| Invalid command configuration                      | `2`   | Correct the input; no successful review                |
| Provider or response-validation failure            | `1`   | Redacted failure; no accepted draft                    |
| Interruption during the provider request           | `130` | Cancelled; prior account usage may be unknown          |

Default `scan`, offline evaluation labels and existing fixture execution allowlists stay unchanged.
No approval token from this command can apply a patch or execute a test. Any future patch/verification
flow needs a separately reviewed design and distinct user decisions.
