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
Offline tests and previews are not a live-model acceptance result. After two unsuccessful attempts
on 2026-09-24 and 2026-09-30, a separately approved live run on 2026-10-01 at `9257bd7` returned
`draft-ready`: one evidence-linked answer and ten structured cases passed host validation.
This completes the narrow read-only provider acceptance, not case-label approval or endpoint testing.
All three attempts and their limits are recorded below. Another provider attempt requires fresh approval.

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
This ID covers that entire sharing envelope and a fresh per-invocation `invocation_nonce`, not just
the request ID. `sharing_content_id` separately identifies the stable displayed content. Identical
content has the same content ID but a different confirmation phrase on each invocation, including
`--preview-only`. An offline preview's phrase cannot approve a later interactive run. Revalidation
reuses that invocation's nonce before its one adapter construction; no CLI nonce override is accepted.
The nonce is a public local challenge, not a secret or authenticated proof of human review.
Codex adds its own harness
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

No further provider attempt was made during that run. No target, application, policy-function or generated-code
execution, HTTP testing or patch application occurred. The feature worktree and original `main` checkout were
clean after the run, and both maintained example source hashes were unchanged. Execution remains
`not-run`, authorization remains `unknown`, and the independent developer labels remain unreviewed.
This failed attempt does not complete live acceptance, broader #35 or a release.

That one-attempt approval was consumed. The source-only diagnostic addition below does not recover
the historical failure's cause or authorize another attempt. The 2026-09-30 attempt below used fresh,
separate source-sharing and account-usage approval. No automatic retry is authorized by either failed result.

## Redacted failure diagnostics — source addition on 2026-09-28

The final result now includes `failure`: `null` when no failure is reported, or an object containing
only the allowlisted strings `stage`, `code` and `turn_start`. This records the adapter's local
failure boundary, not an unfiltered provider error or a proven root cause. For example,
`stage=turn-stream` with `code=protocol-rejected` means a checked protocol condition failed while
processing the turn stream; it does not by itself establish authentication, quota or network failure.

Stages distinguish adapter setup, request validation, startup, configuration, account/model checks,
thread/turn start, turn streaming, response/result validation and cleanup. Unclassified failures use
`unknown`; unsupported or malformed diagnostic values from an adapter are replaced with a safe
fallback. Fixed codes such as `timeout`, `transport-error` and `response-invalid` help distinguish
failure categories without copying exception text.

| `turn_start`    | Local observation                                                                |
| --------------- | -------------------------------------------------------------------------------- |
| `not-attempted` | No local `turn/start` send attempt was recorded.                                 |
| `attempted`     | A local send was attempted; a matching valid turn-start reply was not confirmed. |
| `acknowledged`  | A matching reply with a valid turn ID was confirmed.                             |
| `unknown`       | The available diagnostic does not establish the turn-start state.                |

None of these states attests to the served model, billing, execution or completion. The existing
`application_turn_attempts` is not a count of server-accepted turns. Failed results keep usage,
warning count and retry count `null`; the diagnostic does not infer them from transport progress.
Its three fields never include raw provider messages, logs, exception text, paths, identifiers,
account details or partial model output.

The diagnostic implementation was checked offline and is tracked in [PR #76](https://github.com/casing1/authzest/pull/76);
that implementation itself was not a new live-model result, a release or completed acceptance. Cancellation still propagates
to the CLI's exit `130`. The version pin, sharing envelope, limits and no-retry rule remain unchanged;
diagnostics grant no additional provider, source, tool or execution authority.

## Live attempt on 2026-09-30

The source CLI at commit `324505d446bc25d78072b83fe23c4c3d4b7a24ed` was tried once with Codex
`0.153.0`, the existing managed ChatGPT login and the exact requested model `gpt-6-astra`.
Fresh consent covered the same two public source snapshots, policy and static evidence, at most
one application-issued turn and 120 seconds. The sharing envelope remained
`share-eb98405cadcdc6234501d513dec8be6c37f1e4c06a50438b260ab40d38c481a7`.

The CLI returned `review-failed`, exit `1`, after `84767.8105` ms (about 84.8 seconds), with no
accepted draft. Its redacted diagnostic was `stage=response-validation`, `code=response-invalid`,
`turn_start=acknowledged`. This identifies the local response-validation boundary and a matching
valid turn-start reply; it does not identify the exact rejected field, content or validation condition.
The raw response was not retained. This result does not establish authentication, quota or network
failure, nor independently attest to the served model, billing or target execution.
Static control-flow inspection shows that this stage follows a matching `turn/completed` event with
`status=completed`, no reported turn error and exactly one bounded final message. This supports a
host-observed protocol completion before local validation failed, not valid JSON, semantic correctness
or an accepted review result.

Returned model identity, usage, warning count and retry count were `null`/unknown.
`application_turn_attempts=1` records the local workflow attempt, not a server-accepted turn count
or usage cap. No AuthZest retry, model fallback, target/application/policy/generated-code execution,
HTTP test or patch application occurred. Both maintained example source hashes and the original
clean `main` checkout were unchanged. Execution remains `not-run`, authorization remains `unknown`,
and the independent developer labels remain unreviewed.

This fresh one-attempt approval is now consumed. Live acceptance, broader #35, merge and release
remain incomplete. The subsequently approved offline follow-up below does not authorize another
provider attempt. The 2026-09-24 failure's cause remains unknown, and the newer diagnostic does not
reconstruct it.

## Offline contract alignment — prompt version 2

The source follow-up adds fixed validation reason codes without retaining rejected provider output.
The failure object still has exactly three fields: `stage`, `code` and `turn_start`. A recognized
owner-review validation failure can now identify the first failed rule with one of these codes:

| Code                           | Local validation category                                      |
| ------------------------------ | -------------------------------------------------------------- |
| `validation-json`              | JSON decoding or JSON-value validity                           |
| `validation-budget`            | Bounded input or result limits                                 |
| `validation-shape`             | Required object, field, collection or type shape               |
| `validation-text`              | Bounded, nonblank text and allowed characters                  |
| `validation-duplicate`         | Identifiers, references or scopes that must be unique          |
| `validation-question-coverage` | Coverage of the requested question set                         |
| `validation-status`            | Supported answer status                                        |
| `validation-evidence`          | Allowed or required evidence references                        |
| `validation-abstention`        | Consistent unknown status, null answer and explicit limitation |
| `validation-case-id`           | Bounded synthetic case identifier                              |
| `validation-case-value`        | Allowed synthetic case value                                   |
| `validation-identity`          | Request, source or result identity binding                     |
| `validation-usage`             | Allowed usage shape or value                                   |

These closed codes contain no field values, paths, identifiers or exception text. They describe the
first failing check, not an exhaustive error list or a proven provider-side cause. Unclassified
response-validation failures retain `response-invalid`; malformed adapter diagnostics still receive
a safe fallback. No new code reconstructs either historical response or turns a rejected draft into
an accepted result.

The owner-review prompt is now `owner-policy-review-v2`. The output schema uses nested `anyOf`
branches to align `hypothesis` with a nonblank answer and `unknown` with a null answer plus at least
one explicit unknown. It also represents supported text/control-character limits and citation-list
minimums. Nullable synthetic subject/report identifiers still allow empty or whitespace-only strings
as negative-case data, but not control characters; they are not normalized into valid identities.
The prompt makes required source/policy citations and the bounded case-data rules explicit.

This schema design follows the documented Structured Outputs subset, including nested `anyOf`
and supported string/array constraints, rather than unsupported conditional composition.
See the official [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).
This is not confirmation that the pinned Codex `0.153.0` transport accepts the revised schema in a
live call. Host validation remains authoritative and fail-closed: exact evidence coverage, uniqueness,
UTF-8 validity and global serialized-result budgets still require host checks and are not all
expressed by the provider schema. Conservative regex anchors can also allow a terminal newline
that the host rejects in identifiers. Surrogate-range exclusions are deliberately absent from
schema regexes because UTF-16 engines can otherwise reject valid non-BMP text; the host still
rejects lone surrogates. The offline conformance suite uses Python `jsonschema`, not the live
provider's schema engine. Its cases distinguish schema-enforced constraints
from these deliberately retained host-only checks; JSON Schema validity is not policy correctness.

Offline verification on 2026-10-01 passed: 2,451 full-suite tests, the 531-test portable CI subset,
and 79 schema/host conformance cases. Five separate JavaScript Ajv schema checks and non-BMP
regex checks in default/Unicode modes also passed. Source CLI preview/decline and fake-provider
failure serialization passed without a real provider. Timeout regressions now expire the real test
deadline at the observed phase rather than depending on startup speed; product timeouts are unchanged.
Ruff, 14 documentation-checker tests, Markdown formatting and the 54-document / 26-pair / 936-link
audit passed. These are offline results, not live provider or policy-correctness evidence.

No provider/account call was made during this offline follow-up. At that point live acceptance remained pending;
the separately approved successful run is recorded next.
The prompt/schema change changes the preview's `sharing_id`; the two
historical one-attempt approvals remain consumed and do not cover the new envelope. Inspect the new
preview and obtain fresh bounded approval before any further provider attempt. Version pin, source
scope, timeout/turn limits, no-retry behavior and all separate execution/application boundaries are
unchanged. This source-only work does not merge PR #76 or publish a release.

## Successful live review on 2026-10-01

The source CLI at `9257bd7cbe8ebe06f03b963e51fafdd5547c5e64` used trusted Codex `0.153.0`,
the existing managed ChatGPT login and the exact requested model `gpt-6-astra`. Fresh maintainer
approval covered one application-issued turn, at most 120 seconds, and only the displayed public
`main.py`/`policy.py` snapshots, policy, static evidence, instructions/schema and limits. The assistant
compared the complete preview and entered its exact sharing phrase under that approval.

- `draft-ready`, exit `0`, after `73982.08925` ms (about **74.0 seconds**), with `failure=null`.
- One answer and **ten** structured cases passed the source CLI's request, evidence, schema and final
  result validation. The answer retained `hypothesis`, stated that no source change was supported,
  and separated pure-policy observations from unknown authentication and endpoint enforcement.
- Returned identity: provider `codex-app-server`, model `gpt-6-astra`, adapter `0.1`, prompt
  `owner-policy-review-v2`. This is the negotiated thread model, not independently attested serving.
- Provider-reported usage: **7,994 input / 2,242 output tokens**; one warning and zero retry
  notifications. This is observed usage, not a token/dollar cap or billing attestation.
- `application_turn_attempts=1`; no AuthZest retry, model fallback, patch, HTTP test or target,
  application, policy-function or generated-code execution. Both maintained source hashes and the
  original clean `main` checkout were unchanged. The feature worktree was clean immediately afterward.
- Sharing ID: `share-25714d98829317ec630c87264ea9595618f7fd1db25ce5dd99598c4be54bc044`.
  Request ID: `request-c7767829b1d516f91f7ceaaa0cfae276f9485d96930296703e658a910251c90c`.

The returned case IDs and suggested expectations were:

| Case ID                | Suggested expectation | Policy boundary                                       |
| ---------------------- | --------------------- | ----------------------------------------------------- |
| owner-read             | allow                 | Authenticated exact owner with the literal read scope |
| nonowner-admin         | deny                  | Admin scope does not override ownership               |
| unauthenticated-owner  | deny                  | Ownership and scope do not replace authentication     |
| missing-principal      | deny                  | Missing principal context                             |
| missing-report         | deny                  | Missing report context                                |
| wildcard-only          | deny                  | Wildcard does not replace literal `reports:read`      |
| blank-identities       | deny                  | Equal whitespace-only identifiers remain invalid      |
| empty-report-id        | deny                  | Report identifier must be nonblank                    |
| no-owner-normalization | deny                  | A trailing-space identity is not normalized           |
| exact-padded-owner     | allow                 | Nonblank padded identities match exactly              |

The assistant compared these suggestions with the displayed policy source without executing it;
that review does not make them user-approved or independent evaluation labels. Cases remain
`model-authored`/`unreviewed`, execution `not-run`, and authorization `unknown`. The fixed developer
matrix was not shared or changed. This single success does not establish future provider reliability
or recover either earlier response's exact rejected condition.

The exact code head had all ten GitHub checks passing, including 2,451 Linux tests, 513 Windows
tests with 18 expected unsupported POSIX-reader skips, frontend checks and CodeQL.
[CI evidence](https://github.com/casing1/authzest/actions/runs/36809340356).
The assistant's latest-commit source review found no additional regression. Historical automated
Codex PR reviews cover older heads and are not treated as acceptance of this code.
[PR #76](https://github.com/casing1/authzest/pull/76) tracks final-head reviews, documentation checks and merge.
Published alpha.3, package version and broader #35 remain unchanged. This one-call approval is consumed.

## Review follow-up: fresh invocation confirmation

The code review at `299e651` identified that the earlier content-only sharing phrase could be copied
into another identical invocation. The [review thread](https://github.com/casing1/authzest/pull/76#discussion_r4152362908)
is addressed by a fresh 128-bit random nonce per invocation, included in its displayed `sharing_id`.
The runner rebuilds the preview with that same nonce before constructing its one single-use adapter.
A captured old phrase is rejected before any adapter/provider use, even when the model, timeout,
request and sharing content are identical. The content hash remains separate for comparison.

This follow-up changes only local confirmation and result metadata, not the model's request,
instructions, prompt, output schema, transport, deadline, source snapshots or execution boundaries.
The local nonce is not sent as task data to Codex and does not create an authenticated approval
service or prevent deliberate automation by a caller controlling the process and its current input.
Historical phrases recorded above are evidence of those earlier runs, never reusable approval.
Offline tests cover fresh identities, stale-phrase rejection, same-nonce revalidation and the real
source CLI with a fake App Server reading its actual displayed challenge. No new live provider run
was made; the 2026-10-01 success remains evidence at `9257bd7`, not a live run of this follow-up.
Follow-up verification passed: **2,463** full offline tests in 163.18 seconds, **542** portable-subset
tests and **152** focused owner-CLI/schema tests. Ruff and Markdown formatting passed, as did the
14 documentation tests and 54-document / 26-pair / 936-link audit. Final-head CI and automated
re-review remain separate merge gates.

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
