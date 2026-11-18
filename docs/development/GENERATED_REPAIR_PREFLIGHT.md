<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_PREFLIGHT.md">한국어</a>
</p>

# Generated repair runtime metadata — fixed local Engine queries

[Documentation index](../README.md) · [Runtime profile](GENERATED_REPAIR_RUNTIME_PROFILE.md) ·
[Input staging](GENERATED_REPAIR_STAGING.md)

## Scope — 2026-11-18 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) foundation adds a private local
Engine metadata reader and a bounded supplied-data comparator. The offline regression suite uses
fake sockets, endpoint metadata and clocks; it invokes no real engine, plugin, socket, generated code
or AI. The source phase executor now uses this reader within the
[session](GENERATED_REPAIR_SESSION.md) and explicit
[CLI file workflow](../guides/GENERATED_FILE_WORKFLOW.md), connected under PR #170. The pure lifecycle
model remains a separate simulation. Source integration is implemented; current rebuilt-image and
installed end-to-end acceptance remain pending under #152. These source tests are not an executed
PoC or verified repair.

## Why a dedicated Engine transport

Docker CLI `v29.0.0` calls `ListPlugins` before formatting `docker info`; plugin metadata executes
installed binaries, including system directories outside an empty `--config`. A JSON template or
closed environment does not remove that path. We therefore do not use CLI `info`, an SDK with
ambient discovery, `curl`, a shell or another helper executable.

The reader uses only the explicit profile Unix endpoint and these fixed GET requests:

| Operation              | Fixed request                                                |
| ---------------------- | ------------------------------------------------------------ |
| Version                | `/version`                                                   |
| Engine information     | `/v<declared API>/info`                                      |
| T, A, B image metadata | `/v<declared API>/images/<that role's exact sha256 ID>/json` |

There is no caller-selected method, path, header, tag or query, redirect, proxy, DNS, retry, build,
pull, install, container create/start or host execution fallback. This avoids CLI plugin dispatch;
it does not establish that a Unix endpoint is trusted or cannot forward elsewhere.

## Transport bounds and current endpoint

The transport checks no-symlink parent core identities and the full socket identity before the
connection and after close. It accepts only an owned/root socket under the documented trusted-OS
assumption; shared sticky parent directories remain possible. The returned pin contains the nine
socket identity fields and a digest of the bounded parent chain. All five responses must bind the
same pin. Checks detect changes, not atomicity against a hostile concurrent same-user writer or
authenticated peer/daemon provenance.

One caller-owned absolute setup deadline and original phase deadline govern the whole sequence.
They are not refreshed per query. The existing proposed limits remain 10 seconds of cumulative
setup/readiness within the original 40-second phase; the current phase/session integration accounts
for earlier work. A synchronous coordinator hook is checked immediately before each connection. It is
not consent or a new reusable execution decision. Synchronous OS calls have no universal preemption
guarantee, and closing a socket is not the lifecycle's additional guest-cleanup budget.

HTTP parsing bounds each header block to 16 KiB/32 fields and each body to 64 KiB. All raw response
bytes, including framing, share one 256 KiB budget across the five requests. The narrow parser accepts
Content-Length, exact chunked framing or connection-close bodies and requires complete framing and
EOF. Conflicting/duplicate headers, unsupported encodings, truncation, extra bytes and budget/time
exhaustion refuse. Acquisition, connection, request and close uncertainty remain separate; the first
failure/cancellation is retained and successful cleanup never erases an earlier failure.

## Metadata comparison, not runtime readiness

`normalize_runtime_metadata` accepts only the exact ordered five response objects and bounded JSON.
Supplied frames remain caller-supplied data. `observe_runtime_metadata` coordinates the fixed reader
and records query/contact disposition separately; an injected fake cannot establish authenticated
observations. Neither returned result alone grants readiness or a live session capability. The active
phase uses fresh direct reader observations under the current session decision; exported JSON cannot
reopen a session or authorize application.

Comparisons bind the advertised API range, Linux platform, matching version/info server version,
declared engine identity and exact role image IDs/architectures. The engine identity preimage is
canonical JSON with `schema_version: "1.0"`, `kind: "generated-repair-engine-identity"` and
`engine_id` from `/info`'s `ID`; its UTF-8 SHA-256 must match the profile declaration.

Only bounded selected metadata and response-body hashes are retained. Image config, daemon security
options and cgroup fields are **declarations observed in metadata**, not proof of effective resources,
seccomp, namespace/mount restrictions or image file contents. Matching IDs/labels do not verify the
dependency lock, recipe or maintained guest assets. No actual supported Engine version/image set is
invented by the fake tests. Local CLI executable/config identities remain unobserved because this
reader does not execute that client. The enclosing phase performs its own separate client/config
identity checks; those checks must not be attributed to the metadata response.

The separate [host archive comparison](GENERATED_REPAIR_IMAGES.md) can compare supplied rootfs
catalogs with maintained assets and exact wheel payloads without extracting or running them. It
reports granular file observations and retains unverified pip-generated files; even a match keeps
whole contents/configuration/readiness false. Metadata reader results cannot substitute for those
file observations, and neither helper authenticates a supplied export's image identity.

Results never grant readiness, generated execution or application authority: `ready`,
`execution_authorized` and `verified_fix` remain false, authorization unknown and generated runtime
not run. Exported JSON is historical data, not a resumable receipt or before baseline. Raw daemon
information and local endpoint details should remain private; no automatic public upload is added.

## Integration and remaining acceptance

### Endpoint-only bootstrap, without invented image IDs

The private `_generated_repair_bootstrap.py` API provides `normalize_engine_bootstrap` for two
supplied frames and `observe_engine_bootstrap` for the fixed reader. It accepts an explicit canonical
Unix endpoint without constructing a full `RuntimeProfile`. Only `GET /version` followed by fixed
`GET /v1.51/info` is allowed; the advertised minimum/maximum API range must include `1.51` before
the second query. Unsupported API/platform data stops the sequence without negotiation or retry.

Both queries share the original setup/phase deadlines and 256 KiB wire budget. The first response's
endpoint pin is rechecked before and after the second query's trusted hook, before connection, and
the returned pins must agree. Socket cleanup still does not establish guest cleanup or peer identity.

The separate bootstrap result records an observed, **unpinned** engine identity/hash;
`profile_created`, `images_inspected`, `identity_pinned`, `ready`, `execution_authorized` and
`verified_fix` stay false. It provides no image IDs, recipe/lock contents, effective-capability proof
or public CLI workflow. [Pinned candidate image inputs](GENERATED_REPAIR_IMAGES.md) remain a separate offline
source check, not a ready image set. Local endpoint/daemon observations are private; this guide adds
no publication of operational records.

### Runtime acceptance still pending

Stopped-create inspection, bounded attach/start/capture, exact guest cleanup and current session/CLI
decisions are connected in source. Metadata observations still cannot replace actual image-content
review or the image-owned pre-import kernel guard. The guard's network correction permits only
strict lo-only or exact maintained default-tunnel fallback facts: non-loopback fallbacks must be
administratively DOWN, operstate DOWN and iflink0, with positive unique indexes and stable bounded
before/after fixed proc/sysfs snapshots. Unknown/active/changed/malformed facts refuse with exit 78.
It opens no socket/netlink and changes no NET_ADMIN, sysctl or network template.

The supported claim is only no active non-loopback interface observed at entry; it is not a claim
about absent IP addresses/all routes, measured external connectivity or isolation proof. The common
asset and six recipe pins changed, so current rebuilt/reviewed T/A/B images, current-source installed
generation/before/apply/after/restore acceptance and the read-only results UI remain pending. Default
generation stays proposal-only. This change does not accept #89 risk, finish an issue, change a version
or publish a release.

References: [Docker CLI info source](https://github.com/docker/cli/blob/v29.0.0/cli/command/system/info.go#L78-L105),
[metadata execution](https://github.com/docker/cli/blob/v29.0.0/cli-plugins/manager/candidate.go#L16-L18),
[system plugin directories](https://github.com/docker/cli/blob/v29.0.0/cli-plugins/manager/manager_unix.go#L13-L18),
[Engine API specification](https://docs.docker.com/reference/api/engine/version/v1.51/).
