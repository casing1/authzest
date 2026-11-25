<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/REPOSITORY_HTTP_RUNTIME.md">한국어</a>
</p>

# HTTP runtime input and metadata checks

[Documentation index](../README.md) · [Frozen scope](../development/0.1.0-SCOPE.md) ·
[HTTP private files](REPOSITORY_HTTP_FILES.md) · [HTTP image preparation](REPOSITORY_HTTP_IMAGES.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## Delivery boundary

These private source APIs prepare the separate schema 2.0 HTTP A/B runtime. They preserve the old
v1.0/v1.1 and T/A/B validators. The external CLI remains proposal-only: it does not call these APIs,
create/start guests or apply original files. Tests use owned inert files, memory sockets and supplied
metadata; this delivery performs no actual Engine/model/image/target operation.

The private metadata reader can contact the declared Unix Engine endpoint when explicitly called by
a trusted coordinator. Importing modules, loading a profile or comparing supplied metadata does not
call it. The reader only issues fixed GET metadata requests. It cannot provision images or manage
containers. Matching declarations/reports do not establish image contents, kernel enforcement,
authorization, policy truth, a direct before/after phase or permission to write.

## Private profile and client continuity

`_repository_http_runtime_input` loads only a bounded private HTTP profile file into
`LoadedRepositoryHttpRuntimeProfile`. It requires the distinct `RepositoryHttpRuntimeProfile`, exact
maintained arm64 A/B recipe/lock/assets and the existing empty-config hash. Legacy profiles, T roles,
duplicate fields, malformed encodings and excess bytes are refused.

The loader holds no-follow descriptors, checks safe parent directories, private single-link file
mode/ownership, complete bytes and identities, and repeats these checks through `assert_current()`.
Ordinary edits and same-byte replacements invalidate the handle. Closure releases descriptors and
preserves the file; uncertain cleanup stays uncertain. Detached review data cannot reopen a live
handle or provide runtime authority. POSIX non-frozen source installation is required.

The separate HTTP client pin checks the declared Docker executable, exact private empty configuration
and endpoint identity with the caller's original synchronous deadline checks. It compares bytes,
permissions, membership and identities without launching the executable or connecting a socket.
Current profile/private-input continuity must still be checked by the future operator around each
effect. Synchronous filesystem checks are not atomic CAS against hostile same-user writers or a
whole-filesystem time bound.

## Four fixed Engine documents

`_repository_http_engine_http.read_engine` accepts only the new profile and exactly `version`,
`info`, `image-A` or `image-B`. There is no T lookup, arbitrary URL, body upload, retry or fallback.
It shares the unchanged bounded HTTP framing/clock/endpoint primitives with the earlier reader:

- One caller-held cumulative wire budget and original deadline; no new allowance per query.
- Unix endpoint/parent identity before and after connection, with the current synchronous guard
  immediately before dispatch.
- Bounded strict framing/body decoding, repeated time checks and explicit socket cleanup facts,
  including incomplete acquisition, cancellation, oversized/truncated replies and close failure.

`_repository_http_preflight.normalize_runtime_metadata` compares exactly four supplied frames.
The private `observe_runtime_metadata` requests those same four documents under the original
40-second phase and cumulative 10-second setup limits. Both bind full current profile identity,
daemon/API/platform, A/B image IDs, endpoint identity and bounded image configuration. The existing
daemon-ID digest convention is preserved; it is not authentication of the daemon.

Schema 2.0 HTTP metadata observations keep their own identity. Partial failures retain the validated
prefix, query/contact/cleanup diagnostics and consumed wire count. A metadata match still exports
readiness false, authorization unknown and verified-fix false. Supplied frames and serialized
observations remain unverified history; even directly read daemon metadata cannot prove effective
image contents or kernel resource/isolation enforcement.

Image-inspect `Id` is the configuration digest. Optional `Descriptor` metadata is projected separately
as `manifest_descriptor`, with `platform_manifest_reported` true only for an explicitly reported
matching platform image manifest. An absent descriptor remains `null`; an index/list or a descriptor
without platform does not supply that platform pin. Never fall back to the configuration ID.

## Stopped-container comparison

`_repository_http_container_inspect.validate_stopped_container` accepts an exact
`RepositoryHttpCreatePlan` and bounded supplied Engine object or one-element CLI array. It reconstructs
the complete profile, manifest or request-only schedule and create plan before comparison. Rehashed
mutations, legacy plans and T fields cannot substitute for that reconstruction.

The required `image_manifest_digest` keyword is a separate expected platform-manifest pin, obtained
independently of the stopped report under review. Container `Image` and `Config.Image` still match
the profile's configuration ID; `ImageManifestDescriptor.digest` matches this separate pin. The
[Docker Engine schema](https://github.com/moby/moby/blob/v28.3.3/api/swagger.yaml#L1798-L1818)
distinguishes configuration and manifest digests. The pure API cannot authenticate a supplied pin
or make a descriptor selected from the same untrusted container report independent evidence.

The comparison requires the exact HTTP name/labels/nonces/container/image/command/environment,
never-started state and zero restarts, read-only root, non-root user, fixed capabilities/security
options, private/default namespaces, resource values and disabled ports/devices/restarts/healthcheck:

- A has exactly two read-only private bind mounts: manifest and the selected flat source. It has
  network mode `none` and no stdin.
- B has no bind/input mounts, shares only the exact A network namespace, and has stdin enabled
  without a TTY. Request schedule bytes still need later bounded stdin delivery and EOF.

The stdin expectations follow the [Docker CLI create configuration](https://github.com/docker/cli/blob/v28.3.3/cli/command/container/opts.go).
Actual candidate image/configuration acceptance remains pending. A supplied stopped-configuration
match grants no ownership, direct execution evidence or lifecycle/write permission. The later phase
must record owned intent before create, recheck every current input and clean up each exact owned
guest/local child even after partial failure.

## Direct A → B phase

`_repository_http_phase.execute_repository_http_phase` is the private effectful bridge from a live
private copy to one bounded HTTP observation. A trusted coordinator calls it only with the same
quiescent `RepositoryHttpFileSession` (`copied-before` for **before**, `applied-after` for
**after**), its exact request/response/cases/verification plan, a loaded private profile, a fresh
session nonce, a synchronous dispatch guard and the shared `SessionEvidenceBudget`. Wrong state,
types, asynchronous guards or nonces are refused before any effect.

One phase uses one original 40-second deadline, at most 10 seconds of cumulative setup and a
separate 10-second cleanup window, reusing the maintained `ProcessPool`, journal and budget:

1. Capture the issuer's current private checkpoint, build the request-only schedule and journal
   intent. Pin the client/config/endpoint and read the four fixed Engine documents. Require the
   reviewed image environment/user, runc, cgroup v2, builtin seccomp and reported resource controls.
2. Seal the A input stage, register the owned name, refuse an existing name, create the stopped A
   guest and compare its inspect report against the exact plan and separately read manifest pin.
3. Attach/start A, wait only for its untrusted startup hint, then create B in A's network namespace
   and attach/start it with `--interactive`. The exact schedule bytes bound in B's plan are written
   to stdin followed by EOF. The legacy process input limit stays 512 bytes; only this phase opts
   into the 16 KiB HTTP schedule ceiling, still with nonblocking writes.
4. Decode B's bounded capture strictly against the schedule and exit code. Remove each exact owned
   guest, terminate local children and close the stage, even after failure or interruption.
5. Only then project responses into the closed comparison frame, with actual cleanup states, and
   compare with the host-held case expectations through the existing comparison.

The guard, the issuer's checkpoint recheck, the profile handle and the stage are checked before
every dispatch. A private edit, profile change or guard failure stops the phase and cleanup still
runs. The first transport error aborts the remaining cases as `not-dispatched`; capture errors map
onto the closed `timeout`/`http-framing`/`body-invalid`/`transport-error` set.

The containerd image store reports a single-platform manifest descriptor without `platform`. That
descriptor supplies the manifest pin only when it is a manifest (never an index/list) and the same
image inspect reports linux/arm64. The stopped container must then report the same digest with an
explicit platform. The configuration ID is never used as that pin.

The retained result (`repository-http-phase-result`) records status, failure, `criteria_met`,
owned guests and absence, cleanup errors, metadata, the projected frame and comparison, bounded
command captures, staged-input and evidence paths. `criteria_met` requires a complete, cleaned phase
whose comparison meets the existing before/after criteria. It is retained history: it cannot reopen
a session, authorize a later write or certify the application beyond the reviewed finite cases.
Owned inert-file tests use a fake Docker client and the maintained B capture codec; actual images
and Engine execution are not exercised by those tests.

## Remaining work

Connect this phase to the private before/diff/apply/after CLI coordination and separately implement
final original-file approval, backup, fresh-state/edit-conflict checks and recovery. Actual reviewed
image build/acceptance, installed actual full-flow evidence and saved-result viewing remain open.
These source APIs do not complete the release criteria or publish a release.
