<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/ko/SECURITY.md">한국어</a>
</p>

# Security Policy

## Supported versions

AuthZest is in early development. Security fixes are provided for the latest published `0.1.x` prerelease
and the latest commit on the default branch. Older preview builds are unsupported.

## Reporting a vulnerability

Do not disclose vulnerability details or sensitive source code from a real target in a public issue,
discussion, or pull request.

Use GitHub private vulnerability reporting when it is available for this repository. If no private reporting
channel is visible, contact the maintainer first and ask for a private communication method without including
sensitive details in the initial public message.

Include the following information when practical:

- affected component and security impact
- prerequisites and reproducible steps
- minimal proof of concept that does not expose third-party data
- suggested mitigation or relevant references

The maintainer should acknowledge the report, confirm its scope, and provide an expected response timeline.

## Safe use

Use AuthZest only with source code and environments that you own or are explicitly authorized to test.
Repositories may contain credentials, production data, personal information, or proprietary code.

The default `authzest scan` is a deterministic local source scan. It does not require an API key,
call Codex, execute the target application, or modify its files. Explicitly running `authzest doctor`
can invoke the installed Codex CLI for version/login diagnostics; it does not call a model or approve
source sharing. Review diagnostic output before sharing it.

The separate, opt-in POSIX `authzest codex-fixture` workflow is implemented for a packaged, owned fixture.
It previews the task/source payload, host instructions and output schema before exact-request sharing
approval, then uses a trusted local Codex installation and its existing ChatGPT login. Codex adds its own
harness context. The live workflow accepts only the maintained `main.py` change from `debug=True` to
`debug=False`; it does not accept an arbitrary repository path or edit an existing checkout.
See the [Codex fixture guide](docs/guides/CODEX_FIXTURE.md).

Sharing, applying the exact diff to a fresh private copy, verifying, and restoring require separate
decisions. The default verification plan checks source configuration without executing it.
Selecting `--runtime-check` does not approve execution: after a separate decision, the fixed worker
can execute only matching bundled fixture constants and inspect debug/health behavior. This is not
an OS/network sandbox, an authorization test, or proof of a security fix. Terminal choices and retained
records are not authenticated human-approval receipts. See [runtime verification](docs/guides/RUNTIME_VERIFICATION.md).

Least privilege, explicit user approval, sensitive-data redaction, timeouts, and failure isolation
remain requirements before source sharing. The packaged public fixture is not evidence of general
secret detection or redaction for arbitrary repositories. General repository AI and generated-test
execution remain unsupported by this live workflow. Its timeout and application-attempt limits are
not hard limits on provider-internal retries, tokens, or spending; missing usage remains unknown.

## Threat model and current boundaries

The [repository threat model](docs/reference/threat-model.md) documents inspected source, protected
assets, trust boundaries, assumptions, and review hypotheses. It is not a completed audit or a blanket
finding-suppression list. The authorization policy of an analyzed application is a separate input.

The optional local API scans the workspace selected at server startup; requests cannot choose a new
path. The CLI UI defaults to loopback. No application authentication or tenant isolation is implemented,
so keep the service local and operator-controlled rather than treating it as a public/shared service.
Private fixture copies and their records are retained for inspection; file-state checks and atomic
replacement are not isolation from hostile concurrent same-user writers.

## Security design expectations

- Network requests and external process execution must remain disabled by default.
- Local API endpoints must not turn a caller-controlled path into unrestricted filesystem access.
- Findings must include evidence and distinguish confirmed, suspected, and unknown states.
- Security controls require regression tests before merge.
- Secrets and personal information must never be committed to the repository.
