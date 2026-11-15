<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_PHASE.md">한국어</a>
</p>

# Generated repair private phase executor

[Documentation index](../README.md) · [Session](GENERATED_REPAIR_SESSION.md) ·
[Image inputs](GENERATED_REPAIR_IMAGES.md)

## Current scope — 2026-11-15 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) implementation connects private
input staging, fixed Docker commands, concurrent capture and the host-owned HTTP comparison into
one internal T → fresh A/B phase. Tests use inert files, fake children/pipes and fake Engine replies.
They do not start Docker, import generated Python or establish installed runtime acceptance.

The public generation command and existing preparation-only session remain unchanged and disabled
for generated execution. There is no new public command or runtime-result importer. A future trusted
coordinator must review provisioned image contents and current capabilities, bind each expiring
decision to the actual files/profile, and consume only its directly returned current-call result.
Calling the private executor is effectful; a profile or matching inspect JSON alone is not permission.

## Fixed execution and observation

The controller rechecks the pinned executable, private empty config, local endpoint and current
workspace/stage before dispatch. It journals a fresh owned name/nonce before stopped creation,
captures the full returned ID, and compares stopped inspection with the reconstructed create plan.
The inspected limits, mounts, namespaces, default seccomp selection and inherited image environment
are daemon-reported configuration, **not effective kernel enforcement or whole-image verification**.
Unsupported or ambiguous representations fail rather than being silently treated as equivalent.

It uses the trusted pinned CLI's combined `start --attach` operation with closed stdin and non-TTY
streams. The CLI establishes attachment before starting; the controller records one combined attempt,
not separately observed attachment success. EOF or CLI exit alone is insufficient: completed T/B
also require matching stopped exit/OOM/error inspection. The A stream remains drained while B runs.

A's maintained Uvicorn startup emits `AUTHZEST_A_STARTED` after startup returns with its started flag.
Generated app code can forge this stdout marker. It is only a coordination hint; B still makes its
fixed 21 requests once, without retry, in the exact owned A network namespace. Host controls compare
all 17 cases with the intended before-defect or after-policy profile. T exits 0/1 and its output remain
auxiliary; neither pytest success nor a startup marker proves a repair or authorizes application.

## Shared limits, cleanup and retained evidence

One original phase deadline is 40 seconds, with cumulative setup/readiness limited to 10 seconds.
Terminal cleanup has one additional 10-second deadline shared across all remaining containers and
local children. Each command or role does not receive a fresh phase or cleanup allowance.

All captured CLI stdout/stderr, including create/inspect/cleanup output, share 256 KiB. The normal
phase stops at 224 KiB and reserves 32 KiB for cleanup. After that normal output failure, old local
capture pipes close without claiming complete EOF, preserving room to attempt exact guest removal.
The existing
metadata reader separately bounds Engine wire bytes. A coordinator-owned cumulative 2 MiB evidence
budget charges journal JSON and metadata wire bytes, and reserves 512 KiB for each bounded result
including base64 expansion, even if persistence fails. It spans before and after; the future session
must retain the same budget instance. No capture or cleanup resets it.
Synchronous filesystem, process creation, daemon and kernel operations have no universal time bound.

Exact owned IDs are inspected before forced removal. An ambiguous create is reconciled only through
its pre-recorded unique name and matching ownership labels. No global prune, original checkout mount,
host execution fallback, image pull/build, caller URL or credential forwarding is added. Local CLI
termination does not prove container removal. Failed/unknown cleanup remains a failed phase.

Private journals, bounded raw captures and result records are retained. The first failure survives
later cleanup errors; cancellation propagates with its historical result when available. Exported JSON
keeps authorization unknown, `verified_fix: false`, and source application false. It cannot be imported
to establish a before baseline or unlock a write.

## Next integration

The A launcher and both platform A recipe digests changed. Old A images/receipts are stale for the new
source and must not be relabeled as current. Dependency locks and T/B assets did not change.

Next connect current session decisions to before, exact diff acceptance/application, fresh after and
restore, then perform separately scoped installed acceptance with current images. The read-only local
results UI follows that working CLI path. #152, #153 and the stable release remain incomplete.

References: [Docker CLI start source](https://github.com/docker/cli/blob/v29.4.3/cli/command/container/start.go),
[Uvicorn server source](https://github.com/Kludex/uvicorn/blob/0.54.0/uvicorn/server.py).
