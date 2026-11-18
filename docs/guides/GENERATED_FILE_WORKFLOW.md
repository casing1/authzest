<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/guides/GENERATED_FILE_WORKFLOW.md">한국어</a>
</p>

# Generated repair file workflow

[Documentation index](../README.md) · [Generation contract](../development/GENERATED_REPAIR_CONTRACT.md) ·
[Session contract](../development/GENERATED_REPAIR_SESSION.md)

## Current source status — 2026-11-15 KST

The source CLI connects one current generated proposal to separately decided private-copy checks,
exact source application and recovery. The default generation command remains proposal-only.
This opt-in implementation has offline/mock coverage; current image/kernel feasibility and the
installed end-to-end acceptance are still pending under [#152](https://github.com/casing1/authzest/issues/152).
It is not included in the immutable published alpha.4 release, and #150/#153 remain incomplete.

The scope is the one maintained synthetic ownership scenario, one application file and one generated
test. It is not an arbitrary repository runner, a host pytest fallback, a browser approval flow or
a general repair engine.

## Review the input offline

The file flow requires a POSIX non-frozen source installation and an existing private runtime
profile. There is no automatic image build/pull, profile generator or bundled ready profile.
The file must be owned by the current user, regular, mode `0600`, single-link, no-follow and at most16 KiB.
The loader binds current bytes/inode/parents and maintained platform recipe, dependency-lock and
guest-asset pins. Invalid input stops before account use.

The following is an offline example with a placeholder profile path; replace it only with a profile
whose actual client and immutable images you have reviewed:

```bash
authzest codex-generate --model EXPLICIT_MODEL \
  --file-workflow --runtime-profile /absolute/private/runtime-profile.json \
  --preview-only --json
```

It returns one combined JSON with `sharing_preview` and `runtime_review_preview`; it prompts nobody,
shares nothing and creates no copy. The runtime profile is local-only and is excluded from the
provider request. The default `authzest codex-generate --model EXPLICIT_MODEL --preview-only`
remains the portable sharing preview.

## Separate decisions in the active path

The non-preview option is effectful and requires current rebuilt/reviewed T/A/B images and the
applicable operational review first. An imported profile or typed acknowledgment does not establish
image contents, kernel enforcement or an OS sandbox.

The CLI first displays the entire local runtime review and a fresh invocation/profile-bound phrase.
Declining stops before AI. After approval, the existing complete source-sharing preview requires
its own exact current phrase and permits one adapter attempt. A valid no-change/unknown result
creates no copy. Only a current proposed change reaches these independent plans:

| Stage          | Permitted effect                                                                 |
| -------------- | -------------------------------------------------------------------------------- |
| `copy`         | Create a fresh private before-app, generated test and retained snapshots/journal |
| `before`       | Run T, then fresh A/B and compare all maintained before observations             |
| `source-diff`  | Accept the current exact application-source diff                                 |
| `source-apply` | Replace only reviewed `app.py` bytes in that private copy                        |
| `after`        | Check fresh captured after inputs with T and independent A/B                     |
| `restore`      | Restore exact original before bytes, retaining the test and evidence             |

Every full plan includes current file identities, source/test/diff, profile and prior results.
Its phrase binds the stage, session nonce and plan ID. Each decision is one use with an original
maximum 300-second expiry; waiting or preparing again does not extend it. Enter declines; cancel
cancels that choice. EOF/Ctrl-C/SystemExit stop all further prompts. Already recorded effects remain
visible. A local stage refusal/failure may still offer a separate restore only when the applied
file and cleanup remain confirmed. Nothing restores automatically or overwrites detected edits.

## Interpret the result

Human output summarizes stages, T exits, independent case/request counts, application and recovery.
`--details` includes full metadata; `--json` emits exactly one final stdout JSON while current
plans and interaction use stderr. Raw captures remain in private phase records.

T before exit 1 and after exit 0 are auxiliary observations, not proof of assertion authenticity.
The host independently checks the full 17-case/21-request HTTP profile and exact input bindings.
Only the current direct phase return can establish a session baseline; saved JSON cannot reopen it.
After restoration, a prior after comparison is historical, not a pass for the restored before file.
Authorization remains unknown and `verified_fix: false`. An uncertain write reports `applied: null`
with an explicit `current_copy_state`; it is not a false/no-effect result. A historical application
may remain true after confirmed restoration.

## Runtime and remaining acceptance

Before target/tool imports, each maintained image entry checks supported kernel-reported controls:
PID 1/nonroot, seccomp/no-new-privileges/zero capabilities, cgroupv2 CPU/memory/swap/PID limits,
read-only root/input, bounded tmpfs and a closed network-interface contract. The strict lo-only path
is retained. A second path permits only source-defined default tunnel fallbacks whose names, types
and flags exactly match the maintained allowlist. Each non-loopback interface must be administratively
DOWN with operstate DOWN and iflink0; indexes must be positive and unique. Bounded before/after facts
from fixed proc/sysfs paths must remain stable. Unknown, active, changed or malformed facts refuse
with exit 78 before target imports.

The network observation is only **no active non-loopback interface observed at entry**. It does not
establish the absence of IP addresses or all routes, measured external connectivity, independent
namespace identity or isolation proof. The check opens no socket/netlink channel and adds no
NET_ADMIN, sysctl or network-template change. The host still applies its phase/capture/cleanup limits
and exact object ownership.

This network fix changes the common asset used by every T/A/B image and all six platform recipe
pins, so current rebuilt/reviewed images are required. Copying new declared hashes into an old profile does not update an image.
The shared limits remain phase 40 s, cumulative setup 10 s, cleanup 10 s, captured output 256 KiB
(normal 224 KiB plus cleanup 32 KiB) and retained session evidence 2 MiB with reserved recovery bookkeeping.
Synchronous filesystem/kernel calls have no universal wall-time guarantee.

This source change performs no live AI/Docker/generated-code run, new image provisioning,
operational patch or release. Next validate the exact installed flow with current images, then connect
the read-only local results UI under [#153](https://github.com/casing1/authzest/issues/153).
