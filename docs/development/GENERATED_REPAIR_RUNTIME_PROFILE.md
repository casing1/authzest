<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_RUNTIME_PROFILE.md">한국어</a>
</p>

# Generated repair runtime profile — offline declarations and create plan

[Documentation index](../README.md) · [Guest source](GENERATED_REPAIR_GUESTS.md) ·
[Lifecycle model](GENERATED_REPAIR_LIFECYCLE.md)

## Scope — 2026-11-13 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) slice validates supplied local
engine/image declarations and builds fixed **stopped-create argument data**. It does not execute
Docker, inspect a daemon/image/file, provision dependencies, create/start a container, run generated
code or activate the executor/session. #152 remains open. A valid profile is not runtime readiness.

The private source API provides `RuntimeProfile`, `ContainerCreatePlan`, `validate_runtime_profile`
and `build_container_create_plan`. Profiles and plans can be constructed or imported by a caller;
they are unverified data, not consent, an attestation, a reusable live session or a before baseline.
The builder revalidates supplied profile content rather than trusting a wrapper's type alone.

## Bound declarations, not observed identities

The closed profile declares an absolute Docker executable and SHA-256, one explicit local Unix
socket, an owned Docker config directory, the hash of an exact empty JSON config (`{}\n`), a daemon
identity hash and an explicit API version. It also declares `linux/amd64` or `linux/arm64` and T/A/B
immutable local image IDs, dependency-lock/recipe hashes and exact expected maintained guest assets.
No tag, automatic model/platform substitution or caller-selected command is supported.

Expected guest asset digests are bound to the current maintained source. They do **not** demonstrate
that a supplied image contains those files. Image ENV, entry point, startup hooks, anonymous volumes,
architecture, installed dependencies and contents still need a separately reviewed operational check.
No actual image IDs, dependency lock or supported daemon version are furnished by this change.

The template selects an explicit Docker `--config` and `--host`; the proposed subprocess environment
contains only the declared `DOCKER_API_VERSION`. It inherits no HOME/PATH, proxy, context, TLS,
credential or alternate configuration variables. The supported declaration syntax is API `1.41`
through `1.99`, not a claim that every version/engine in that range is tested or usable.

The future caller must create and identity-check the empty config directory/file and reject other
entries or edits. Merely declaring a config hash does not prevent a symlink, replacement, proxy
configuration or credential helper. Likewise a Unix endpoint can forward elsewhere: local syntax
does not prove a trusted local daemon, socket identity or privilege boundary.

## Fixed role plans

| Role | Read-only source mounts                                           | Network                                  | Fixed guest entry   |
| ---- | ----------------------------------------------------------------- | ---------------------------------------- | ------------------- |
| T    | Only app and generated test leaves from one declared staging root | none                                     | `test_launcher.py`  |
| A    | Only app leaf from that root                                      | none                                     | `app_launcher.py`   |
| B    | None; app/test/staging arguments forbidden                        | Exact full A container ID namespace only | `relay_launcher.py` |

T/A input paths are derived fixed leaves, not arbitrary per-file mount arguments. Paths must be
canonical bounded ASCII absolute paths; commas, controls, traversal and other mount-grammar
ambiguities are rejected even though no shell is involved. Staging paths/hashes remain declarations:
the builder does not establish that files are captured, private, unchanged, owned or outside a checkout.
B receives only 1–40,000 remaining milliseconds, never the host's absolute clock epoch.

Names and fixed labels derive only from bounded session/role hex nonces. The future host must still
generate fresh nonces and persist the owned name before create; a caller's reused nonce is not freshness.
The immutable argument template selects `container create`, pull-never, non-root UID/GID 65532,
read-only root, cap-drop-all, no-new-privileges, private IPC/cgroup namespaces, no init/restart/logging/
healthcheck/TTY/interactive/published ports and a fixed tmpfs. CPU/memory/swap/PID/shm budgets retain
the existing design. Entry is fixed `/usr/local/bin/python -I -B` plus the role script.

These are proposed flags, **not effective runtime enforcement**. No invented private-PID or default
seccomp flag is used: the actual default/effective PID isolation, seccomp, controller support, runtime,
mounts, volumes, network and limits must be checked against a supported stopped-container profile.
There is no start/attach/stop/remove argument builder, transport or automatic cleanup in this slice.

## Result and remaining gates

Plans have status `planned-not-executed`, provenance `caller-supplied-unverified`,
`runtime_invoked: false`, `execution_authorized: false`, authorization `unknown` and
`verified_fix: false`. Neither these data nor matching fake inspections unlock execution or writes.
The original shared host phase/readiness/cleanup limits remain authoritative; no timer is started here.

Reviewed client/socket/config/daemon identities and images/locks, effective capabilities, safe actual
input staging, stopped-create inspection, bounded attach/start/readiness/capture and confirmed guest
cleanup, durable evidence, session decisions and exact installed acceptance remain pending. No
provider/source sharing, operational patch/restore, issue completion, risk acceptance or release occurs.

References: [Docker create](https://docs.docker.com/reference/cli/docker/container/create/),
[Docker CLI configuration](https://docs.docker.com/reference/cli/docker/),
[Docker seccomp](https://docs.docker.com/engine/security/seccomp/).
