<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/SECURITY.ko.md">한국어</a>
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

The current deterministic local analyzer does not require an API key. Before a future Codex adapter sends any
content outside the local process, it must clearly show which files and prompts will be transmitted and apply
least privilege, explicit user approval, sensitive-data redaction, timeouts, and failure isolation.

## Security design expectations

- Network requests and external process execution must remain disabled by default.
- Local API endpoints must not turn a caller-controlled path into unrestricted filesystem access.
- Findings must include evidence and distinguish confirmed, suspected, and unknown states.
- Security controls require regression tests before merge.
- Secrets and personal information must never be committed to the repository.
