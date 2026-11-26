<p align="center">
  <strong>English</strong> ·
  <a href="docs/i18n/ko/SECURITY.md">한국어</a>
</p>

# Security Policy

## Supported versions

AuthZest is in early development. Security fixes are provided for the latest published `0.1.x` release
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

The separate source-only `authzest repo-suggest` command accepts an explicit external root,
one Python repair target, a user-provided policy document and at most four selected Python context
files. It captures bounded regular UTF-8 files without symlink traversal or automatic discovery,
parses those exact bytes, and shows the complete prompt/schema/source before a fresh typed sharing
decision. The decision expires after 300 seconds; every selected input is compared again before one
adapter call. Existing authentication remains managed by the trusted Codex installation.

Selected source/policy, comments and model output are untrusted data. Explicit selection does not
detect secrets, so the operator must read the full sharing preview. Request IDs bind content, not a
person. Generated tests/source and host-derived diffs stay inert, and structural AST validation
shows neither that tests run nor that the policy is right. This command grants no copy,
application, execution or GUI authority. Treat unintended file disclosure, scope substitution,
stale sharing and reachable generated-code execution as real boundary failures, even though older
workflows used synthetic fixtures. This section accepts no risk and excludes no findings. See the
[external-project guide](docs/guides/REPOSITORY_PROPOSALS.md).

## External single-file repair (`repo-fix`)

`authzest repo-fix` is the 0.1.0 flow that can change a file outside this repository, so its
boundaries matter most. It runs only from a non-frozen source or wheel installation on macOS arm64
with Docker Desktop and a private runtime profile prepared by the setup script.

- What is shared: After a typed sharing decision on the full preview, Codex receives the one
  selected source file and the policy file. The reviewed case file, which holds the expected answers,
  never leaves the host. Codex runs through its App Server in a read-only sandbox without network
  access, with an empty temporary directory as its working directory, and uses your existing
  ChatGPT login.
- Model output: The PoC request and the replacement source are untrusted data. The PoC must
  equal the designated regression case or the flow stops. The replacement source runs only inside
  the isolated A container, never on the host.
- Containers: A has network mode `none`, a read-only root filesystem, a non-root user, fixed
  capabilities and two read-only bind mounts (manifest and the selected file). B shares only A's
  network namespace and receives the request schedule over stdin. Each phase has a 40-second
  deadline, at most 10 seconds of setup and a 10-second cleanup window. Containers carry owned
  names and are removed exactly; uncertain cleanup is reported, not hidden.
- Decisions: Sharing, copy, before check, private apply, after check and original write each
  need their own typed single-use code, which expires after 300 seconds.
- Original write: Before writing, AuthZest rechecks that the original and policy are unchanged
  since capture and refuses any edit as a conflict. It replaces the file atomically and keeps its
  mode, group, ACL and extended attributes. It refuses a file owned by another user, a file with
  flags, or metadata it cannot reproduce. The recovery record lives in a private `0700` directory
  under `~/.authzest/recovery` with read-only copies of the before and after bytes.
  `authzest repo-restore` restores only while the file still holds exactly the applied bytes, so
  later edits are never overwritten.
- Saved results: The `--json` result contains the shared source and policy text and private
  paths. Save it with `umask 077`. The dashboard viewer drops private paths when it displays a
  result, but do not upload results to a hosted viewer.

Limits: the file-state checks are not atomic against a hostile process running as the same user,
and container isolation relies on Docker Desktop. Matching the reviewed cases shows only that those
requests behave as expected; it is not a security audit of the application. Identities are
synthetic test headers. Treat disclosure of files beyond the selected pair, acceptance of a PoC
that differs from the regression case, guest network access, host execution of model output, writes
outside the selected file and a restore that overwrites later edits as real boundary failures. See
the [external fix guide](docs/guides/REPOSITORY_HTTP_FIX.md) and the
[HTTP runtime reference](docs/reference/REPOSITORY_HTTP_RUNTIME.md).

## Threat model and current boundaries

The [repository threat model](docs/reference/threat-model.md) documents inspected source, protected
assets, trust boundaries, assumptions, and review hypotheses. It is not a completed audit or a blanket
finding-suppression list. The authorization policy of an analyzed application is a separate input.

The ordinary local API scans the workspace selected at server startup and displays imported results;
requests cannot choose a new path. Its existing read-only routes provide no application authentication
or tenant isolation. Keep the service local and operator-controlled.

The separate `authzest ui --ai-runtime-config /ABSOLUTE/PRIVATE/runtime.json` mode connects one
maintained owner-read scenario to the existing generated-repair engine. Active operation is disabled
by default. This POSIX source mode requires numeric loopback, one application instance and no reload.
The operator fixes the private runtime configuration at launch. Every `/api/ai` request requires the
fresh launch capability and exact Host/port checks; mutation additionally requires matching Origin
and JSON. The private launch URL carries its token in a fragment, which the browser removes and
retains only in memory. It is not a general user-login or tenant boundary.

Each current runtime, sharing, copy, before, diff, apply, after and restore plan retains a separate
typed decision and the engine's expiry, exact-input and file-state rechecks. A model response or
imported result cannot approve a new operation. Cancellation is cooperative and can leave a copy
requiring recovery after application; it must not silently restore, erase uncertain cleanup or release
the active slot before the owned worker ends. The browser can download its bounded final JSON,
without choosing a server filesystem destination. The GUI uses the existing Codex ChatGPT login and
only coarse login diagnostics; no OAuth tokens, raw account output or auth files enter its API.
See the [local workflow guide](docs/guides/RESULT_VIEWER.md) and
[interactive design](docs/development/GENERATED_REPAIR_CONTRACT.md).

Review reachable browser-to-local request paths that could disclose plans, consume model usage or
issue an unintended file-stage decision. The synthetic target does not exempt the HTTP controller,
request gates or copy/guest consumers from security review. These boundaries accept no risk, exclude
no findings and do not add general repository execution.

Private fixture copies and their records are retained for inspection; file-state checks and atomic
replacement are not isolation from hostile concurrent same-user writers.

## Security design expectations

- Network requests and external process execution must remain disabled by default.
- Local API endpoints must not turn a caller-controlled path into unrestricted filesystem access.
- Opt-in active requests must preserve launch capability, Host/Origin checks and one-shot current
  decisions; importing a result must remain read-only.
- Findings must include evidence and distinguish confirmed, suspected, and unknown states.
- Security controls require regression tests before merge.
- Secrets and personal information must never be committed to the repository.
