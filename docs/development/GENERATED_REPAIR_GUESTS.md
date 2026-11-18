<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_GUESTS.md">한국어</a>
</p>

# Generated repair guest entry points — offline source

[Documentation index](../README.md) · [HTTP relay](GENERATED_REPAIR_HTTP_RELAY.md) ·
[Lifecycle model](GENERATED_REPAIR_LIFECYCLE.md)

## Scope — 2026-11-18 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) slice adds maintained standalone
guest launcher **source**, tested only with fake dependencies and sockets. No guest, application,
generated test, real socket, image or engine is started by these tests. The explicit
[CLI file workflow](../guides/GENERATED_FILE_WORKFLOW.md) connects current session decisions to the
phase executor, while default generation remains proposal-only. Current-image installed acceptance
is pending; #152 remains open and no actual PoC or repair is verified by these source tests.

The [guest assets](../../runtime/generated_repair/) are intended for a later reviewed image, not a
host fallback or an installed CLI command. They deliberately do not import the AuthZest package:
importing a runner package would also import host machinery. Each image must contain only its
required assets/dependencies, not the host control oracle, source checkout, credentials or records.
The later [pinned image inputs](GENERATED_REPAIR_IMAGES.md) add Dockerfiles and dependency locks,
and the [private phase executor](GENERATED_REPAIR_PHASE.md) connects internal transport with fake-only
acceptance. The source opt-in flow requires current rebuilt/reviewed images; this document does not
establish runtime acceptance. Do not run these assets on the host to bypass missing isolation.

## Fixed roles and inputs

| Role | Fixed entry         | Input / behavior                                                                            |
| ---- | ------------------- | ------------------------------------------------------------------------------------------- |
| T    | `test_launcher.py`  | Only `/input/app.py` and `/input/tests/test_generated_ownership.py`; fixed pytest selection |
| A    | `app_launcher.py`   | Only `/input/app.py:app`; one loopback ASGI server on `127.0.0.1:8765`                      |
| B    | `relay_launcher.py` | Maintained request-only codec; no app/test mount, expected labels or caller URL             |

Entry invocation requires Linux, isolated Python with `-I -B`, the exact
`/opt/authzest-guest/` script layout and UID/GID `65532`. T/A accept no extra arguments; B accepts
only one canonical integer remaining-time value in milliseconds, from 1 through 40,000.
These checks are diagnostics, **not containment, image attestation or execution consent**. The future
host must still inspect the exact stopped-container recipe, mounts, namespaces and resource controls.

Before target/tool imports, the common guard reads fixed kernel paths and refuses unsupported
PID/nonroot, seccomp/no-new-privileges/capability, cgroup, mount and interface settings with exit 78.
It checks no target contents and creates no process/socket. This is a narrow supported-property check,
not a resource stress benchmark, escape proof or independent A/B namespace attestation.

The network guard retains strict lo-only acceptance and adds a closed default-tunnel fallback path.
Names, types and flags must match maintained source literals; every non-loopback fallback must be
administratively DOWN, operstate DOWN and iflink0, with positive unique indexes. Fixed proc/sysfs
snapshots are bounded and compared before/after. Unknown, active, changed or malformed data refuses
with exit 78 before a target is imported. This means only **no active non-loopback interface observed
at entry**, not absence of addresses/all routes, measured external connectivity or isolation proof.
The check uses no socket/netlink, NET_ADMIN, sysctl or network-template change.

This common-asset change invalidates all T/A/B common pins and six platform recipes. Current images
must be rebuilt and reviewed. A typed runtime review or updated declaration cannot substitute for image contents.

The launchers clear inherited environment before loading dependencies and expose the fixed trusted
asset directory explicitly (`-I` does not retain the script directory). T/A import image-owned
pytest/Uvicorn before exposing `/input` to app imports. No shell or model-selected command is used.

T disables pytest plugin autoload, configuration/addopts/environment plugins, conftest discovery
and the cache provider. It selects one exact test path with importlib mode. Its native exit code and
raw stdout/stderr are **untrusted auxiliary observations**. An exit code of 1 does not by itself
establish an assertion-level ownership reproduction; 0 does not prove a repair. Report authenticity,
source review and installed acceptance remain separate. No report plugin or trusted pass count is added.

A fixes ASGI3, asyncio, h11, one worker, no reload, proxy headers, WebSockets, access log or lifespan
hooks. It adds no health route. An import, startup log or successful process start is not trusted HTTP
readiness evidence. The maintained startup emits `AUTHZEST_A_STARTED` only after server startup;
the app can forge that stdout hint. The private controller uses it for scheduling B while enforcing
the cumulative readiness budget; independent complete HTTP observations remain necessary.

B uses numeric IPv4 loopback and a fresh TCP socket per fixed request, without hostname lookup,
proxy configuration or `create_connection`. Ownership reaches the codec before connection dispatch,
so failed connection/setup/cancellation still takes the owned-stream close path. It never reconnects
or retries a request. It emits bounded complete/partial capture JSON for host validation; target logs
are not relay facts. A socket close does not establish guest termination/removal.

## Separate clock domains, one authoritative host deadline

The Mac host and Linux engine guest need not share a monotonic epoch. Passing the host's numeric
absolute deadline into the guest would therefore be incorrect. The future host retains its original
40-second phase deadline, including T and A/B setup/capture, and the cumulative 10-second startup
sub-budget. B receives only a snapshot of the **remaining duration**, derives one guest-local
absolute deadline and never refreshes it for another connection, request or chunk.

That guest timer is an advisory cooperative bound, not a replacement or extension of the original
host deadline. Startup/transport delay must not buy more host time. The future host must terminate
and confirm cleanup at its original limits regardless of the guest's clock or output. Callback,
filesystem, daemon and kernel operations still have no universal preemption guarantee.

## Remaining operational work

Staging, stopped-create inspection, attach/capture/cleanup and session/CLI decisions are implemented
and covered with fakes/inert files. Current rebuilt image contents, kernel feasibility and separately
scoped installed before/apply/after/restore acceptance remain pending. Generated test output alone
cannot unlock a baseline or write; the host requires complete current independent observations and
confirmed cleanup. Exported data keeps `verified_fix: false`; the demo actor header is not authentication.

No provider/source sharing, real generated import/collection/execution, operational application or
restoration, risk acceptance, issue completion, version change or release is performed by this slice.

References: [pytest reference](https://docs.pytest.org/en/stable/reference/reference.html),
[Uvicorn settings](https://uvicorn.dev/settings/),
[Python socket API](https://docs.python.org/3.12/library/socket.html).
