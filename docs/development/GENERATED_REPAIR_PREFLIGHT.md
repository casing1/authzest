<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_PREFLIGHT.md">한국어</a>
</p>

# Generated repair runtime metadata — fixed local Engine queries

[Documentation index](../README.md) · [Runtime profile](GENERATED_REPAIR_RUNTIME_PROFILE.md) ·
[Input staging](GENERATED_REPAIR_STAGING.md)

## Scope — 2026-11-15 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) foundation adds a private local
Engine metadata reader and a bounded supplied-data comparator. Maintained tests use fake sockets,
endpoint metadata and clocks. No real engine, plugin, socket, generated code or AI is invoked during
development validation. The existing executor, lifecycle simulation, session and public CLI remain
unconnected to this reader. #152 stays open; this is not an executed PoC or verified repair.

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
setup/readiness within the original 40-second phase; future session integration must account for
earlier work. A synchronous coordinator hook is checked immediately before each connection. It is
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
observations. Neither path changes the disabled executor or creates a live session capability.

Comparisons bind the advertised API range, Linux platform, matching version/info server version,
declared engine identity and exact role image IDs/architectures. The engine identity preimage is
canonical JSON with `schema_version: "1.0"`, `kind: "generated-repair-engine-identity"` and
`engine_id` from `/info`'s `ID`; its UTF-8 SHA-256 must match the profile declaration.

Only bounded selected metadata and response-body hashes are retained. Image config, daemon security
options and cgroup fields are **declarations observed in metadata**, not proof of effective resources,
seccomp, namespace/mount restrictions or image file contents. Matching IDs/labels do not verify the
dependency lock, recipe or maintained guest assets. No actual supported Engine version/image set is
invented by the fake tests. Local CLI executable/config identities remain unobserved because this
reader does not execute that client.

Results never grant readiness, generated execution or application authority: `ready`,
`execution_authorized` and `verified_fix` remain false, authorization unknown and generated runtime
not run. Exported JSON is historical data, not a resumable receipt or before baseline. Raw daemon
information and local endpoint details should remain private; no automatic public upload is added.

## Remaining integration

Actual interoperability and reviewed image provisioning/contents, effective stopped-container
inspection, bounded attach/start/capture and exact guest cleanup, durable session decisions, installed
generation/before/apply/after/restore acceptance and the read-only results UI remain pending. This
change does not accept #89 risk, finish an issue, change a version or publish a release.

References: [Docker CLI info source](https://github.com/docker/cli/blob/v29.0.0/cli/command/system/info.go#L78-L105),
[metadata execution](https://github.com/docker/cli/blob/v29.0.0/cli-plugins/manager/candidate.go#L16-L18),
[system plugin directories](https://github.com/docker/cli/blob/v29.0.0/cli-plugins/manager/manager_unix.go#L13-L18),
[Engine API specification](https://docs.docker.com/reference/api/engine/version/v1.51/).
