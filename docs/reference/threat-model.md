<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/threat-model.md">한국어</a>
</p>

# AuthZest threat model

[Documentation index](../README.md) · [Security policy](../../SECURITY.md) ·
[Codex fixture](../guides/CODEX_FIXTURE.md) · [Runtime verification](../guides/RUNTIME_VERIFICATION.md)

## 1. Overview

Reviewed on 2026-09-14 against casing1/authzest source revision
2521ca5f23030561e2b2117900943557db6a6706. Source anchors below refer to that baseline.
This is an architecture-backed review guide, not a completed security audit, a finding list,
or proof that a fix is effective. It models AuthZest itself, not the access-control policy of
a FastAPI application being analyzed.
The baseline was checked with an independent, offline architecture review; that is not audit coverage.

The supported product is a local, single-operator, CLI-first source analyzer. Ordinary scans
collect static evidence without importing the target or calling a model. The optional API/dashboard
scans a workspace selected at server startup. A separate POSIX Codex workflow shares one packaged
fixture after approval, accepts only its exact debug-setting replacement, and offers independent
copy-application, verification, and restoration decisions. General repository AI, generated
regression-test execution, and edits to an existing checkout are not supported by that workflow.

### Components and inspected source

| Component                    | Role and evidence                                                                                                                                                                                                                                                                                                    |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Static core                  | Source discovery and reports: [src/authzest/analyzer/repository.py:28](../../src/authzest/analyzer/repository.py#L28); repository-local AST reads: [src/authzest/parser/repository.py:20](../../src/authzest/parser/repository.py#L20).                                                                              |
| CLI and local API            | User-selected scan input: [src/authzest/cli.py:43](../../src/authzest/cli.py#L43); startup-bound API: [src/authzest/api/app.py:27](../../src/authzest/api/app.py#L27).                                                                                                                                               |
| Optional review contracts    | Caller-owned approval and disabled adapter default: [src/authzest/runner/review.py:30](../../src/authzest/runner/review.py#L30); these helpers do not authenticate a human.                                                                                                                                          |
| Live fixture coordinator     | Sharing and distinct decisions: [src/authzest/runner/codex_fixture.py:98](../../src/authzest/runner/codex_fixture.py#L98); exact output validation: [src/authzest/codex/fixture_draft.py:185](../../src/authzest/codex/fixture_draft.py#L185).                                                                       |
| Codex adapter                | Single-use, version-pinned external transport: [src/authzest/codex/app_server.py:535](../../src/authzest/codex/app_server.py#L535).                                                                                                                                                                                  |
| File application             | In-process session state: [src/authzest/runner/fixture_apply.py:44](../../src/authzest/runner/fixture_apply.py#L44); private copy operations: [src/authzest/runner/_fixture_workspace.py:49](../../src/authzest/runner/_fixture_workspace.py#L49).                                                                   |
| Verification and publication | Fixed workers: [src/authzest/runner/fixture_check.py:158](../../src/authzest/runner/fixture_check.py#L158), [src/authzest/runner/fixture_runtime.py:120](../../src/authzest/runner/fixture_runtime.py#L120); conditional publication: [.github/workflows/release.yml:132](../../.github/workflows/release.yml#L132). |

### Effective resources and authority

Paths below are derived locations, not inspected user credentials or actual temporary directories.
Separate process startup and a clean working directory do not establish OS-level isolation.
Repository import indexing uses root and root/src ([parser:66](../../src/authzest/parser/repository.py#L66)).
Reports include the absolute root and raw parse-error strings, so exported reports can reveal local
metadata ([models:186](../../src/authzest/models.py#L186)). Ordinary wheel/pipx installs do not bundle
the dashboard; a source-relative fallback is not proof that assets exist in every installation.
The configured ChatGPT backend is https://chatgpt.com/backend-api, not an independently verified route.
Codex 0.153.0 is checked at initialization; protocol limits are 256 KiB per JSON message/line,
2 MiB total received data and 4,096 events, with an application timeout of at most 120 seconds
([version:31](../../src/authzest/codex/app_server.py#L31),
[initialize:372](../../src/authzest/codex/app_server.py#L372),
[protocol:298](../../src/authzest/codex/app_server.py#L298)).

| Deployment or workflow              | Resource or capability                           | Configuration and precedence                                                                       | Safe effective value or location                                                                               | Readers, writers, or recipients                                                                    | Enforcing control                                                                                      | Evidence or unknowns                                                                                                                                                                                                                                                                                               |
| ----------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CLI scan                            | Read Python source                               | Explicit path, expanded and resolved                                                               | Selected root; regular, non-symlink Python files below it                                                      | Local analyzer; report recipient                                                                   | Skipped directories and local-source checks; AST parsing only                                          | [analyzer:28](../../src/authzest/analyzer/repository.py#L28), [parser:20](../../src/authzest/parser/repository.py#L20); not a hostile concurrent-writer sandbox.                                                                                                                                                   |
| CLI UI                              | HTTP access to a fixed workspace report          | Explicit workspace or current directory; CLI overwrites AUTHZEST_SCAN_ROOT                         | Default listener 127.0.0.1:8000; selected root captured at startup                                             | Clients reaching the local API                                                                     | Request cannot select a new filesystem target                                                          | [cli:234](../../src/authzest/cli.py#L234), [cli:258](../../src/authzest/cli.py#L258), [API:43](../../src/authzest/api/app.py#L43); no application authentication/origin gate.                                                                                                                                      |
| Direct ASGI application             | Same workspace scan                              | Explicit create_app scan_root, then AUTHZEST_SCAN_ROOT, then current directory                     | Resolved directory captured by create_app; listener is ASGI host configuration                                 | Reachable API clients                                                                              | Same fixed-root endpoint                                                                               | [API:22](../../src/authzest/api/app.py#L22); do not assume CLI loopback defaults apply to another launcher.                                                                                                                                                                                                        |
| Dashboard assets / Vite development | Serve UI; proxy local API                        | Explicit frontend_dist, else frozen bundle or source tree; separate Vite config                    | Explicit directory or _MEIPASS/frontend/dist or source frontend/dist; Vite port 5173 proxies to 127.0.0.1:8000 | Browser and local backend                                                                          | Frontend submits no scan path; API owns root selection                                                 | [API:15](../../src/authzest/api/app.py#L15), [API:50](../../src/authzest/api/app.py#L50), [frontend:54](../../frontend/src/App.tsx#L54), [Vite:4](../../frontend/vite.config.ts#L4).                                                                                                                               |
| Explicit doctor command             | Invoke trusted Codex diagnostics                 | Codex found through PATH; ordinary inherited process environment                                   | Installed executable; version/login metadata, not a model turn                                                 | Local Codex and terminal/JSON recipient                                                            | Five-second command timeout                                                                            | [diagnostics:42](../../src/authzest/diagnostics.py#L42), [diagnostics:73](../../src/authzest/diagnostics.py#L73); successful stdout is surfaced, so do not publish it as necessarily sanitized.                                                                                                                    |
| Approved Codex fixture              | Share source and use account/model authority     | Existing HOME/CODEX_HOME retained; adapter configuration overrides and two effective-config checks | Empty authzest-codex-empty-* cwd; existing Codex-managed account location; built-in OpenAI provider            | Trusted Codex executable and OpenAI                                                                | Exact-request sharing gate, ChatGPT account check, no tools/runtime roots, endpoint-override rejection | [environment:128](../../src/authzest/codex/app_server.py#L128), [config:94](../../src/authzest/codex/app_server.py#L94), [checks:393](../../src/authzest/codex/app_server.py#L393), [draft:570](../../src/authzest/codex/app_server.py#L570); account storage and provider routing are not independently attested. |
| Fixture apply / restore             | Replace one file and retain records              | New private system-temp directory; internal/test caller may supply parent, CLI cannot              | authzest-fixture-*/main.py, before.txt, after.txt, record.json                                                 | Local operator and trusted process                                                                 | Directory 0700; files 0600; no-follow and single-link checks; source/decision rechecks                 | [workspace:56](../../src/authzest/runner/_fixture_workspace.py#L56), [replace:160](../../src/authzest/runner/_fixture_workspace.py#L160), [restore:516](../../src/authzest/runner/fixture_apply.py#L516); retained, not automatically deleted or restartable.                                                      |
| Source-mode static verification     | Fixed AST worker                                 | Current interpreter with -I -S                                                                     | Temporary authzest-configuration-check-* cwd; stdin at most 1 KiB, stdout at most 4 KiB                        | Trusted standard-library worker; validated output to coordinator                                   | Exact fixture allowlist, reduced environment, 5-second startup/I/O plus 1-second cleanup               | [static command/environment:50](../../src/authzest/runner/fixture_check.py#L50), [static execution:158](../../src/authzest/runner/fixture_check.py#L158); no target imports or execution.                                                                                                                          |
| Source-mode runtime verification    | Opt-in fixed runtime worker                      | Current interpreter with -I, permitting trusted site startup and installed dependencies            | Temporary authzest-runtime-check-* cwd; stdin at most 1 KiB, stdout at most 4 KiB                              | Fixed bundled-code probe and installed FastAPI/Starlette/Pydantic; validated result to coordinator | Separate plan approval, exact fixture allowlist, reduced environment, same 5-second/1-second limits    | [runtime command:44](../../src/authzest/runner/fixture_runtime.py#L44), [runtime allowlist:148](../../src/authzest/runner/fixture_runtime.py#L148); no OS/network sandbox or automatic dependency installation.                                                                                                    |
| Frozen verification                 | Reinvoke bundled fixed worker                    | sys.executable with hidden worker command; retain three validated existing _PYI_* values           | Existing executable and _MEIPASS unpack directory; same temporary cwd rules                                    | Trusted binary, bundled dependencies and worker                                                    | Check archive path, unpack path and parent level; same fixture/decision checks                         | [static command/environment:50](../../src/authzest/runner/fixture_check.py#L50), [runtime command:44](../../src/authzest/runner/fixture_runtime.py#L44); consistency checks are not binary attestation.                                                                                                            |
| CI / release                        | Execute reviewed build inputs; publish artifacts | PR/push CI has contents:read; v* tag or manual release workflow                                    | Build artifacts; publication job alone receives contents:write on a tag after prerequisite jobs                | CI runner, dependency registries, action providers, GitHub release users                           | Main/tag check and validate/build/downloaded-artifact gates                                            | [CI:3](../../.github/workflows/ci.yml#L3), [release:35](../../.github/workflows/release.yml#L35), [publish:132](../../.github/workflows/release.yml#L132); hosted protection settings were not inspected.                                                                                                          |

## 2. Threat model, trust boundaries, and assumptions

### Assets, actors, and objectives

Protect source confidentiality, unrelated files and user edits, Codex account authority and usage,
proposal/decision integrity, truthful evidence and failure records, local availability, and release
integrity. An operator choosing a root or approving a request is not the same actor as a source author
or the model supplying text.

A malicious source author can control files, paths, declarations and comments in a repository the
operator selects; an untrusted model response can control returned text. Neither thereby gains
approval authority, filesystem write permission or a tool capability. An API caller can request a
scan only if it can reach the service. A PR contributor can propose code/build changes, but does not
automatically receive publication authority. Do not assume an attacker already owns the operator's
account, interpreter, trusted Codex installation, or release token.

The invariants to preserve are:

1. Default scans remain source-only and offline. Static declarations, valid JSON, empty reports,
   successful exits, and a debug/health check do not prove authorization correctness.
2. Sharing, applying, verifying and restoring remain separate choices. Login, model output, a flag
   selecting runtime verification, or a proposal identifier alone does not authorize another stage.
3. The live CLI accepts only the maintained source and exact debug-setting change. The model cannot
   select arbitrary source paths, commands, tools, output identities, or a broader write target.
4. Apply and verify decisions are bound to content/plan identity, checked for expiry and consumed in
   the current process; recheck file state before writes and execution. Restoration must not replace
   detected intervening user edits. Failed or unconfirmed writes/checks must not be reported as success.
5. The runtime worker executes only matching bundled constants, not arbitrary supplied code. Its
   in-memory ASGI health probe is not an exploit test or a general runner.
6. Release authority stays separate from untrusted contributions; documentation never grants
   permission to transmit source, run code, publish artifacts or modify account settings.

The coordinator's checks are at [codex_fixture:142](../../src/authzest/runner/codex_fixture.py#L142)
and [codex_fixture:208](../../src/authzest/runner/codex_fixture.py#L208); decision/source checks are at
[approval:94](../../src/authzest/runner/approval.py#L94),
[application:474](../../src/authzest/runner/fixture_apply.py#L474) and
[verification:311](../../src/authzest/runner/fixture_apply.py#L311).
The runtime execution boundary is at [_runtime_worker:107](../../src/authzest/runner/_runtime_worker.py#L107).

### Assumptions, exclusions, and open questions

- CLI and Python-library callers already act with the local user's authority. Exact terminal phrases
  and in-memory records are workflow gates, not authenticated human receipts. Internal workers and
  the hidden packaging smoke can be invoked directly by that same user; visibility is not authorization
  ([cli:202](../../src/authzest/cli.py#L202)). Application helpers can accept caller-owned fixture text;
  only the live CLI and fixed verification paths impose the packaged-source allowlist.
- Trust the operating system, interpreter/site startup, installed or bundled dependencies, Codex
  executable and its managed account storage. Codex inherits HOME/CODEX_HOME despite an empty cwd.
  Its no-tools/read-only settings restrict the model session, not the trusted provider process's
  account/network access. No endpoint, served-model, executable or human-identity attestation is claimed.
- Exclude hostile same-user concurrent writers from the copy workflow. Private permissions and atomic
  replacement are not compare-and-swap against such an actor. Local source scans likewise are not an
  immutable filesystem snapshot. Their aggregate file/byte/time budget needs a separate review before
  unattended use on hostile repositories; the Codex/worker limits do not bound static scanning.
- The API has no authentication, tenant isolation or explicit origin/Host protection in create_app.
  Keep it local and operator-controlled. Public/shared deployment is unsupported; browser-to-loopback
  abuse needs a concrete reachable request/read path before it is treated as a vulnerability.
- Windows scanning is distinct from POSIX fixture application/checking. An exact configuration/health
  demo is not an authentication/ownership PoC. Test fixtures may intentionally contain unsafe settings;
  do not flag their presence alone, or exempt the production code that consumes them.
- The updated root [SECURITY.md](../../SECURITY.md#safe-use) describes the implemented opt-in fixture
  transport while retaining the privacy/default-off requirements. A packaged public fixture does not
  demonstrate general-source secret detection or redaction.
- The adapter bounds application attempts, protocol bytes/events and time, but not all internal
  provider retries or monetary usage. Missing usage remains unknown. Codex-hosted PR reviews are a
  separate service from this adapter; their settings, remote retention and account state were not
  inspected or changed by this document.
- The release guide states that binaries are not signed or notarized
  ([release scope](../releases/RELEASING.md)). Matching checksums do not authenticate a binary and
  checksum replaced together. Hosted tag/branch protections and external approvals remain unverified;
  a manual release-workflow run against a tag can publish, unlike a manual run against main.

## 3. Attack surface, mitigations, and attacker stories

These are prioritized review hypotheses, not validated vulnerabilities. Priority means investigation
order, not a finding severity. Each claimed capability gain still requires source-backed validation.

| Priority | Scenario and capability gain                                                                      | Prerequisites                                                                   | Impact                                                               | Existing controls                                                                                            | Mitigation                                                                                                                      | Evidence                                                                                                                                                                                    |
| -------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | Source paths or repository size cause out-of-root reads or resource exhaustion                    | Operator selects attacker-controlled source; any race needs a concurrent writer | Confidentiality or local availability                                | Local regular-file checks and AST-only imports; no global scan budget established                            | Keep roots narrow; test link/race behavior and introduce explicit scan budgets before unattended expansion                      | [parser:20](../../src/authzest/parser/repository.py#L20), [analyzer:28](../../src/authzest/analyzer/repository.py#L28)                                                                      |
| 1        | Model text attempts to expand source sharing, use tools or choose an arbitrary patch              | Explicitly approved fixture turn; untrusted response                            | Unapproved disclosure, writes or execution if independent gates fail | Fixed request, exact replacement, strict identities; server requests rejected; effective tool/context checks | Preserve host validation and rejection tests; never treat prompt instructions as the only control                               | [draft:185](../../src/authzest/codex/fixture_draft.py#L185), [protocol:298](../../src/authzest/codex/app_server.py#L298), [config:393](../../src/authzest/codex/app_server.py#L393)         |
| 1        | Stale/changed proposal or file reuses approval and overwrites another state                       | Approval followed by altered content/plan or attempted reuse                    | Integrity and recoverability                                         | Bound decisions, expiry, single consumption, private descriptors, checked replacement and separate restore   | Keep checks at sensitive consumers; reject changed state; never replay a journal as consent                                     | [approval:94](../../src/authzest/runner/approval.py#L94), [apply:474](../../src/authzest/runner/fixture_apply.py#L474), [replace:160](../../src/authzest/runner/_fixture_workspace.py#L160) |
| 1        | Verification accepts generated commands/source or reports an unrun check as a fix                 | New runner/fixture support or invalid worker response reaches coordinator       | Host execution or false security assurance                           | Separate plan decision; exact source/worker identity; fixed constants; bounded output/status validation      | Expand through reviewed allowlists and failure tests; design real confinement before arbitrary execution                        | [verify:311](../../src/authzest/runner/fixture_apply.py#L311), [worker:107](../../src/authzest/runner/_runtime_worker.py#L107)                                                              |
| 2        | Reachable API exposes workspace metadata or permits repeated expensive scans                      | Another actor can reach listener or establish a browser-origin attack path      | Disclosure or availability; no tenant boundary is promised           | Loopback CLI default and startup-fixed root; no caller path                                                  | Do not bind publicly; add and test authentication/origin/resource controls before shared deployment                             | [cli:234](../../src/authzest/cli.py#L234), [API:27](../../src/authzest/api/app.py#L27)                                                                                                      |
| 2        | Provider output/diagnostics or retained records mislead a reviewer or leak metadata when shared   | Operator consumes untrusted prose or publishes local output                     | Wrong decisions or disclosure                                        | Live flow escapes JSON text and redacts transport failures; records retain distinct statuses                 | Treat explanations as untrusted; inspect/redact exported diagnostics and records; do not apply live-output guarantees to doctor | [output:58](../../src/authzest/runner/codex_fixture.py#L58), [diagnostics:99](../../src/authzest/diagnostics.py#L99), [session:44](../../src/authzest/runner/fixture_apply.py#L44)          |
| 2        | Stream/retry behavior consumes unexpected time or account usage                                   | Operator has approved a live request                                            | Local availability and usage                                         | One application turn, deadline, event/byte caps, process-group cleanup                                       | Keep unknown usage explicit; separately authorize live acceptance checks; do not advertise a spending cap                       | [transport:535](../../src/authzest/codex/app_server.py#L535), [protocol:298](../../src/authzest/codex/app_server.py#L298), [cleanup:149](../../src/authzest/codex/app_server.py#L149)       |
| 2        | Untrusted contribution/build dependency crosses into release authority or substitutes an artifact | A specific CI/dependency/gate failure, not assumed maintainer compromise        | Supply-chain impact to release users                                 | Read-only CI token; tag/main and artifact gates; write permission isolated to publish                        | Review privileged workflow changes; verify dependency/build provenance and downloaded bytes; recheck hosted rules separately    | [CI:7](../../.github/workflows/ci.yml#L7), [release:35](../../.github/workflows/release.yml#L35), [publish:132](../../.github/workflows/release.yml#L132)                                   |

## 4. Severity calibration (Critical, High, Medium, Low)

| Level    | Conditional example                                                                                                                                   | Counterexample / required evidence                                                                                                                                   |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Critical | Demonstrated compromise of trusted published binaries affecting many users, or similarly broad privileged execution through an actual boundary bypass | A malicious PR proposal, unsafe test fixture, or already-compromised maintainer account alone does not establish this impact. Prove the publication/capability path. |
| High     | Attacker-controlled source/model output obtains unapproved sensitive-file access, arbitrary code execution, or writes outside the approved target     | Local operator-approved actions and the exact bounded debug-setting change are not an unauthorized gain. Prove input control, reachability and the failed gate.      |
| Medium   | A reachable untrusted-input path causes meaningful bounded denial of service, limited disclosure or material evidence corruption                      | Unsupported public deployment and scan incompleteness alone are not proof. Establish affected data, exposure, repetition and effective limits.                       |
| Low      | A limited security-relevant information exposure or integrity weakness with narrow impact and restrictive prerequisites                               | Pure cosmetic errors and hypothetical control failures are not automatically vulnerabilities. Explain the actual protected asset and capability gain.                |

Assess confidence separately from impact; preserve unknown prerequisites rather than inflate severity.
Revisit this model when source selection, adapter/tool access, approval identities, file application,
worker execution, API exposure or release authority changes. Update both languages and source anchors
together. This document adds no permission, changes no setting and certifies no security property.
