<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/REPOSITORY_HTTP_VERIFICATION.md">한국어</a>
</p>

# HTTP policy cases and A/B preparation

[Documentation index](../README.md) · [Frozen scope](../development/0.1.0-SCOPE.md) ·
[Proposal CLI](../guides/REPOSITORY_PROPOSALS.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## Current delivery

These source APIs prepare the external single-file HTTP workflow using supplied data, owned inert
files and fake collaborators. They do not build images, open an Engine/socket, execute an app or
grant file operations. The CLI's `--http-poc` remains proposal-only. Its result is not yet accepted by
the GUI importer. Existing v1.0/v1.1, T/A/B and packaged demonstration interfaces keep their own
identities and behavior.

The new mode has separate schema 2.0 case, plan, schedule, supplied-phase, manifest and runtime-profile
kinds and `repository-http-*` identities. It has A/B roles only; no generated test file, pytest result
or fabricated T identity is needed. Numerical schema versions alone do not establish compatibility.

## Independent cases and exact PoC correspondence

`authzest.runner.repository_http_cases` exposes `RepositoryHttpCaseSet`,
`build_repository_http_cases(data)` and `validate_repository_http_cases(cases)`. A document binds
the selected-source/policy hashes and selection identity to the explicit HTTP interface. It contains:

- Four to eight ordered, uniquely identified cases with one literal GET each and exact typed
  before/after status plus JSON or empty-body expectations.
- One designated regression whose supplied before and after expectations differ, with its reason.
- Authorship and assumptions, and coverage for owner, non-owner, anonymous, normal use and public
  intent. Owner, non-owner and normal-use coverage are mandatory; anonymous/public may instead have
  an explicit not-applicable reason.

Those are declarations, not authenticated human review or established policy truth. Status codes,
strict JSON types and bounded bodies preserve distinctions such as `true`, `1` and `1.0`. A normal
dependency declaration or a source-level scope does not infer any expected answer.

`build_repository_http_verification_plan(request, response, cases)` validates the complete current
schema 2.0 request and response. For a proposed change, the model's unique header-array records are
explicitly normalized to a header map and the GET method/path/headers must exactly match the
designated independent case. Otherwise planning is refused; expectations are not generated from the
model, and a new case is not silently appended. A validated no-change/unknown/refused response returns
`None` without requiring cases.

`RepositoryHttpVerificationPlan` binds the full request/response identities, before/after source
hashes, HTTP interface, entire case set, designated regression, raw PoC hash and normalized request.
Raw header-array order still changes the proposal identity, even when its normalized request matches.
`validate_repository_http_verification_plan` reconstructs the whole closed plan.

## Request-only observation and supplied comparisons

`prepare_repository_http_observer_schedule(..., phase="before" | "after")` projects all case IDs and
requests, never source, policy, expected answers or model explanations. The observer schedule uses
`repository-http-observer-schedule` and `repository-http-verification-plan-*`; the old schedule entry
rejects these identities.

The stdlib-only `_repository_http_transport` exposes `validate_http_observer_schedule`,
`encode_http_observer_request` and `capture_repository_http_poc`. It shares the unchanged bounded
HTTP parser/clock primitives with the earlier mode, but accepts only the new schedule. It has no
default socket implementation. A trusted caller must inject connected streams and a clock:

- Fixed loopback `127.0.0.1:8765`, literal GET paths and allowlisted synthetic `test-*` identity headers.
- One original phase deadline, fresh stream per case, no redirect/retry and bounded framing/body/I/O.
- The complete planned denominator remains in the result; the first error leaves the suffix
  not-dispatched. Close is attempted once for every acquired stream, including after expiry or cancellation; failed
  closes remain unconfirmed.

Raw close facts concern streams, not A/B guest cleanup. Expiry before acquisition is not HTTP
dispatch; a later host adapter must retain its setup/timeout fact. Callbacks are trusted and cannot
be preempted by this synchronous codec. The result remains caller-supplied/unverified data.

`decode_repository_http_phase_candidate` and `validate_repository_http_phase_candidate` accept a
separate `RepositoryHttpPhaseCandidate`: declared source/interface/case/PoC bindings, every ordered
observation and A/B cleanup values `confirmed`, `unknown` or `failed`. After an error, only a
not-dispatched/phase-aborted suffix is accepted. T/pytest fields and omitted/reordered cases are refused.

`compare_repository_http_phase` compares typed values against the host-held expectations. Invalid
frames preserve the full planned denominator. Even a fully matching supplied frame remains
`supplied-unverified`, execution `not-run`, authorization `unknown`, `verified_fix=false`,
`live_evidence=false` and `writes_authorized=false`. It cannot substitute for a current directly
returned live phase or authorize a patch.

## Source-only manifest and A/B declarations

`_repository_http_manifest` is a bounded stdlib-only codec for one flat source descriptor and the
explicit HTTP interface. It has no policy, expectations, test or client fixture. Input paths are
`/input/manifest.json` and `/input/project/<source.py>`. IDs and hashes are declarations until a
separate live staging layer measures the files and current session.

`_repository_http_runtime_profile` exposes `RepositoryHttpRuntimeProfile`, `validate_runtime_profile`
and `build_container_create_plan`. The latter returns `RepositoryHttpCreatePlan` data, not a launcher:

| Role | Declared inputs and limits                                                                                                                          |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| A    | Read-only manifest and source mounts; network-none; explicit ASGI app, lifespan off and no authentication overrides; 512 MiB, 1 CPU and 64 PIDs.    |
| B    | No input mounts; bounded request-only stdin plus EOF; only A's network namespace, with separate PID/mount namespaces; 128 MiB, 0.5 CPU and 32 PIDs. |

Both use the new guest root/name/label namespace, UID/GID 65532, read-only roots, dropped capabilities,
no host ports/credentials/socket mounts and bounded temporary storage. Declarations retain a shared
40-second phase, setup within that phase and additionally capped at 10 seconds cumulatively, and
10 seconds for cleanup. No effective runtime enforcement is claimed by constructing the plan.

`runtime/repository_http/` contains separate maintained guard/A/B source and two arm64 Dockerfiles.
The image manifest pins those bytes, the unchanged dependency/base references and canonical recipes.
Guest guards precede target/tool import; the maintained observer does not import target code or read target source.
The manifest still says **declared-not-built**, image IDs are null and readiness/content verification
are false. This is neither an accepted image nor escape-proof isolation.

## Remaining connection

The [HTTP image helpers](REPOSITORY_HTTP_IMAGES.md) now check maintained inputs, prepare retained
minimal contexts and compare supplied inert exports. The [HTTP private-file APIs](REPOSITORY_HTTP_FILES.md)
add current source-only checkpoints and sealed A inputs. Separate
[runtime input/metadata checks](REPOSITORY_HTTP_RUNTIME.md) prepare HTTP profile/client, fixed Engine
and stopped-container comparisons. Actual image/content acceptance,
current direct host phases and the
approved copy/before/diff/apply/after/restore operator remain pending. Old file sessions require pytest
artifacts and cannot be adopted by inventing test fields. Final original-file application, backup,
edit-conflict refusal and recovery remain required under #152/#150. Installed actual acceptance and
the saved-result GUI connection are later gates; supplied data and offline passes do not close them.
