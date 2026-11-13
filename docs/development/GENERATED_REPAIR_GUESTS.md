<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_GUESTS.md">한국어</a>
</p>

# Generated repair guest entry points — offline source

[Documentation index](../README.md) · [HTTP relay](GENERATED_REPAIR_HTTP_RELAY.md) ·
[Lifecycle model](GENERATED_REPAIR_LIFECYCLE.md)

## Scope — 2026-11-12 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) slice adds maintained standalone
guest launcher **source**, tested only with fake dependencies and sockets. No guest, application,
generated test, real socket, image or engine is started by these tests. The production executor and
session stay disabled for runtime. #152 remains open; no actual PoC or repair is verified here.

The [guest assets](../../runtime/generated_repair/) are intended for a later reviewed image, not a
host fallback or an installed CLI command. They deliberately do not import the AuthZest package:
importing a runner package would also import host machinery. Each image must contain only its
required assets/dependencies, not the host control oracle, source checkout, credentials or records.
There is no Dockerfile, dependency lock, provisioned image, image identity or active engine adapter
in this slice. Do not run these assets on the host to bypass missing isolation.

## Fixed roles and inputs

| Role | Fixed entry         | Input / behavior                                                                            |
| ---- | ------------------- | ------------------------------------------------------------------------------------------- |
| T    | `test_launcher.py`  | Only `/input/app.py` and `/input/tests/test_generated_ownership.py`; fixed pytest selection |
| A    | `app_launcher.py`   | Only `/input/app.py:app`; one loopback ASGI server on `127.0.0.1:8765`                      |
| B    | `relay_launcher.py` | Maintained request-only codec; no app/test mount, expected labels or caller URL             |

Future entry invocation requires Linux, isolated Python with `-I -B`, the exact
`/opt/authzest-guest/` script layout and UID/GID `65532`. T/A accept no extra arguments; B accepts
only one canonical integer remaining-time value in milliseconds, from 1 through 40,000.
These checks are diagnostics, **not containment, image attestation or execution consent**. The future
host must still inspect the exact stopped-container recipe, mounts, namespaces and resource controls.

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
readiness evidence; the future host must enforce its cumulative readiness budget independently.

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

We still need reviewed pinned images/dependency locks and a trusted local engine, safe captured-input
staging with identity rechecks, effective stopped-create inspection, attach-before-start transport,
shared output/time budgets, durable capture and exact guest cleanup, session/decision integration
and separately scoped installed before/apply/after/restore acceptance. Generated test output cannot
unlock a baseline or source write. Matching supplied relay facts remain unverified and
`verified_fix: false`; the demo actor header is not authentication.

No provider/source sharing, real generated import/collection/execution, operational application or
restoration, risk acceptance, issue completion, version change or release is performed by this slice.

References: [pytest reference](https://docs.pytest.org/en/stable/reference/reference.html),
[Uvicorn settings](https://uvicorn.dev/settings/),
[Python socket API](https://docs.python.org/3.12/library/socket.html).
