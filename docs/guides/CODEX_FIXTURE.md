<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/CODEX_FIXTURE.md">한국어</a>
</p>

# Opt-in Codex review of an owned fixture

[Documentation index](../README.md) · [Offline copy demo](FIXTURE_APPLICATION.md) · [AI contract](../reference/AI_CONTRACT.md)

## Scope and current evidence

[#50](https://github.com/casing1/authzest/issues/50) adds a source-checkout command for one maintained
configuration fixture. Live end-to-end verification is **PENDING**. This feature is not in the published
alpha.2 binaries and does not complete [#35](https://github.com/casing1/authzest/issues/35).

AuthZest's task/source payload contains a previewed, packaged `main.py` snapshot, its source evidence,
a declared policy, and one question. The only accepted source draft changes `debug=True` to `debug=False`, preserving every
other character. This is a configuration demonstration, not an authorization finding, exploit PoC,
generated regression test, or verified security fix. There is no arbitrary repository/path input.

The ordinary `scan` command stays offline. The existing offline proposal and copy demos remain scripted,
not AI-generated. General repository AI review, arbitrary patching, and verification execution are not
implemented by this command.

## Run from current source

Use a trusted local Codex **0.153.0** installation with an existing ChatGPT login managed by Codex.
This adapter is version-pinned; other versions are not declared compatible. The live copy workflow is
POSIX-only and does not extend Windows scan support to this command. Choose a model available to your
Codex account; `MODEL` below is a placeholder, not an automatically selected model.

```bash
authzest codex-fixture --model MODEL --timeout-seconds 120
```

The timeout defaults to 120 seconds. Before starting any Codex process, the command displays its exact
`HOST_INSTRUCTIONS`, task/source payload, requested model, and request ID and requires explicit
source-sharing approval bound to that ID. Codex adds its own harness context; this preview does not
claim to show the model's entire context.
Type the displayed `share <request_id>` phrase exactly to approve this request.
Declining or cancelling this step starts no provider process. A successful login never grants consent
to transmit source, apply a patch, or execute verification.

Codex manages its existing login; AuthZest does not read API keys, tokens, or credential files.
See the official [authentication guide](https://learn.chatgpt.com/docs/auth) for Codex login behavior.
The [App Server documentation](https://learn.chatgpt.com/docs/app-server) describes its managed ChatGPT
authentication; the restrictions here are AuthZest's narrower fixture workflow, not general Codex limits.

## One model turn, separate file approval

After sharing approval, the adapter starts the supported local App Server for one application-issued
turn. AuthZest performs no application retry, fallback, or model substitution. Codex's internal transport
retries may still occur. The timeout is not a hard token or monetary limit; usage may be incurred before
a failure or cancellation, and missing usage measurements must remain unknown.

The model receives no tools or environment access; tool requests are rejected. Output is untrusted JSON.
Host validation binds identity and source references and accepts only the exact maintained replacement.
Valid JSON or a correct source citation does not prove that the explanation is true. The host creates
the diff and proposal identity; model text cannot approve its own change.

The transport starts in a clean, empty working directory, accepts only the built-in OpenAI provider
with ChatGPT authentication, and checks effective tool/context settings before the turn. Remote-control
status must be `disabled` in the status read and subsequent notifications; otherwise the flow stops. It limits
protocol output to 256 KiB per line and 2 MiB in total and cleans up its own process group. Runtime
errors are redacted; raw stderr, account email, and conversation transcripts are not saved by AuthZest.
These controls assume a trusted Codex installation, not a sandbox for an untrusted executable.

The requested model identity is checked against the model negotiated at thread start. The summary
records `model_identity_basis: negotiated-thread-model; not independently served-model attestation`.
This is not independent proof of which model served the response.

A valid draft is shown for a separate exact-diff decision. Approval can change only a newly created,
private fixture copy, never the original checkout. Type the displayed `apply <proposal_id>` phrase
exactly; decline/cancel does not apply the draft. Restoration requires `restore <proposal_id>` and
refuses detected intervening edits; it does not overwrite user work. The copy, before/after snapshots,
and `record.json` are retained for inspection; the workflow JSON summary includes request/proposal IDs
and available usage. The file-operation limits
and failure meanings in the [copy application guide](FIXTURE_APPLICATION.md) still apply.

All outcomes retain `verification_status: not-run`. No source code, test command, install hook, or
verification plan is executed. A successful draft or file replacement is not a verified fix. A later
issue must add separately approved, bounded verification before the complete #35 acceptance gate can close.

## Contract compatibility

AI schema `1.1` permits `temperature: null`, meaning no numeric sampling temperature was requested;
the provider manages it. Existing numeric-temperature requests retain schema `1.0`, their identities,
and the existing `AdapterConfig` default of `0.0`. Null is not zero or deterministic generation.
The scan report remains schema `1.2`; no package version or new release is implied by these changes.

Live account/model availability, end-to-end results, token usage, and failure recovery evidence must be
recorded after explicit live validation. They are not established by the offline mocks or this guide.

## Development validation — 2026-09-11

Local Python 3.12 validation passed 957 tests, including 222 new tests. The transport subset includes
85 offline tests with actual fake-server subprocesses and CLI approve/restore and decline flows.
Timeout and cancellation checks observed termination of the test wrapper and its descendant.
Documentation checker tests (14), language/link checks, Ruff, and frontend lint/format/build passed.
The wheel and macOS ARM64 development binary exposed the command and cancelled safely on EOF before
sharing. These artifacts were not published and reused local build dependencies.

A metadata-only preflight against Codex 0.153.0 confirmed ChatGPT login, disabled remote control,
two disabled inherited MCP servers, and a fresh read-only thread with no instruction sources or
runtime workspace roots. It issued **zero model turns** and sent no fixture source. Live model
generation remains **PENDING**; these checks do not establish live end-to-end success or a verified fix.
