<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_HTTP_RELAY.md">한국어</a>
</p>

# Generated repair HTTP relay — offline stream foundation

[Documentation index](../README.md) · [Lifecycle model](GENERATED_REPAIR_LIFECYCLE.md) ·
[Host controls](GENERATED_REPAIR_VERIFICATION.md)

## Scope — 2026-11-12 KST

This is another partial slice of [#152](https://github.com/casing1/authzest/issues/152).
The maintained relay codec reads bounded response facts for the fixed synthetic scenario.
It is **not an active engine adapter**. There is no default socket implementation, executable
module entry point, CLI/API/UI connection, Docker probe/build/pull, generated import/execution,
provider call, file application or restoration. The executor and session remain disabled for runtime.
#152 remains open.

The [stdlib-only relay module](../../src/authzest/runner/_generated_repair_http.py) contains only
the fixed request inputs and protocol/capture logic. It does not import AuthZest, the generated
application, test, maintained expected bodies/statuses or disclosure markers. The separate
[host-only bridge](../../src/authzest/runner/_generated_repair_relay.py) checks its request
projection against the current controls before comparing complete supplied facts. A future relay
image must not package that host bridge/control oracle as guest input.

## Fixed request inputs, host-owned verdicts

The relay owns exactly 21 unique ordered GET requests: owner/cross-owner, missing/empty/unknown
demo actor, missing document and both own → other → own sequences. Request IDs, paths and actor
headers are maintained inputs, not response expectations. Host checks reject drift between those
inputs and the controls. The caller-controlled demo actor is **not authentication**.

Request bytes use literal `127.0.0.1`, fixed port `8765`, `Connection: close` and identity encoding.
There is no caller URL, host, port, method, proxy/configuration, redirect following, decompression
or dependency choice. Each request uses a fresh supplied stream; server state may persist only
within the future independent A application, not from generated-test T into A/B.

The stream factory and synchronous clock are explicit **trusted Python collaborators**. A factory
receives the fixed target and remaining timeout, but this interface cannot prevent it ignoring
those arguments or performing unrelated effects. It is not a sandbox, real socket adapter or
proof of network isolation. Tests supply only maintained in-memory streams.

## Deliberately narrow HTTP profile

The parser supports HTTP/1.1 with a single canonical decimal `Content-Length`, ASCII response
headers and a bounded raw body. It is not a general HTTP client or complete standards implementation.
The framing reference is [RFC 9112 §6.3](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3);
this fixed-fixture profile deliberately rejects some otherwise valid HTTP forms rather than guessing.

| Boundary      | Limit / refusal                                                                                         |
| ------------- | ------------------------------------------------------------------------------------------------------- |
| Status line   | 512 bytes including CRLF; informational/upgrade and bodyless 204/304 unsupported                        |
| Headers       | At most 32; complete wire and represented header blocks at most 4 KiB including terminating CRLF        |
| Body          | At most 8 KiB; bytes retained as base64, never executed or decompressed                                 |
| Framing       | One Content-Length; no transfer coding/chunking, duplicate/comma/missing length or obsolete folding     |
| Completion    | Exact declared body and EOF; truncation and any trailing response bytes rejected                        |
| Whole capture | Bounded wire input, receive calls and serialized complete/partial data; at most 256 KiB per data budget |

Redirect status is recorded as supplied data, not followed. Unsupported content coding, non-ASCII
header text, control characters and malformed/oversized framing fail closed. There is no target
log channel mixed into these response facts. Host output limits and validation remain independent.

## Deadlines, partial results and cleanup

Capture consumes the caller's **original absolute phase deadline**, with at most 40 seconds
remaining, not a new allowance for each request or chunk. It checks the same nondecreasing finite
clock before/after cooperating factory and stream operations and before returning a complete result.
An invalid/reversing clock or exact deadline cannot become successful capture.

Streams are closed on success, protocol/I/O failure, timeout and cancellation. Partial facts and
the first failure are retained separately from close failure. A confirmed stream close is not
container termination/removal. These checks cannot preempt a blocking/malicious Python collaborator
and are not a universal filesystem/daemon/kernel wall-clock guarantee.

The outer T/A/B shared phase/startup/cleanup budgets, cumulative stdout/stderr cap, stopped-create
inspection, staging identities, bounded process attachment and durable evidence still require the
operational adapter. This helper does not grant a fresh phase, verify a local engine or enforce
Docker resources. Serialized output bounds are not measured runtime enforcement.

## Supplied facts are not execution authority

The host bridge accepts only a complete closed current-schedule capture with all 21 ordered facts.
It binds the caller's explicit before/after candidate and current controls, then invokes the existing
data-only comparator. Partial, malformed, reordered, duplicate, stale or cleanup-failed data cannot
be accepted as a complete observation set. Imported data remains caller-supplied and unverified.

Even a matching scripted before/after profile has execution `not-established`, authorization
`unknown` and `verified_fix: false`. It establishes no session before baseline, source-diff
acceptance, apply/restore authority or provider provenance. Generated pytest reports remain
untrusted auxiliary data and do not enter this relay.

Before an active installed workflow, we still need reviewed local engine/images, image-owned
server/test launchers, fixed real socket entry, exact effective-recipe and file/staging bindings,
capture/persistence/guest-cleanup integration and separately scoped runtime acceptance. No course
completion, release or real PoC/repair observation is claimed by this offline foundation.
