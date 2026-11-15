<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_IMAGES.md">한국어</a>
</p>

# Generated repair images — pinned inputs, not built images

[Documentation index](../README.md) · [Guest entries](GENERATED_REPAIR_GUESTS.md) ·
[Runtime metadata](GENERATED_REPAIR_PREFLIGHT.md)

## Scope — 2026-11-15 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) foundation records candidate
image inputs for the separate T/test, A/application and B/relay roles. It adds offline input checks,
private context preparation and host archive comparison, not a builder or generated-code executor.
#152 remains open.
The manifest keeps `status: "candidate-not-built"`, `image_ids: null` and
`contents_verified: false`; input consistency cannot manufacture ready images or a live profile.

These repository helpers perform no build, pull, load, layer retrieval, container creation/start,
generated-code execution, Docker CLI/Engine request or AI call. There is no new public AuthZest
command, runtime decision or release. Operator-local receipts are separate private records; they do
not replace the portable manifest's unbuilt-candidate status.

## Recorded candidate inputs

The source directory [runtime/generated_repair/images](../../runtime/generated_repair/images/)
contains one [manifest](../../runtime/generated_repair/images/manifest.json), six platform/role
dependency locks, six Dockerfile recipes and five retained raw base-image JSON documents. The
candidate base is `docker.io/library/python:3.12.16-slim-bookworm`; recipes use the recorded child
manifest digest, not the mutable tag, for each platform.

| Role | Additional locked wheels per platform | Intended role                                           |
| ---- | ------------------------------------- | ------------------------------------------------------- |
| T    | 20                                    | FastAPI application plus the generated pytest test      |
| A    | 14                                    | FastAPI application served by the fixed guest launcher  |
| B    | 0                                     | Maintained relay using the base Python standard library |

Both `linux/amd64` and `linux/arm64` have explicit inputs. Their selected dependency sets contain
22 distinct package names in total. B adds no wheels; this does not make the base operating system,
Python installation or inherited files dependency-free or verified.

The guest candidate selects `pytest==9.0.3` from the reviewed release metadata. This is separate
from the host development environment: its existing pytest constraint is unchanged. The fixed guest
launcher still selects its exact test with `-c /dev/null`; the image inputs do not broaden test
discovery, add model-selected dependencies or modify the launcher source.

## What the offline check establishes

[scripts/generated_image_inputs.py](../../scripts/generated_image_inputs.py) checks the closed
manifest, role/platform sets, package metadata and dependency selection against maintained source.
Recorded raw OCI/Docker JSON bytes must follow the declared index → selected child manifest →
config digest chain. The index selects the declared Linux architecture/variant; the selected config
must match its OS/architecture and exact recorded Python environment binding. The checker also compares the current guest-asset bytes,
hash-pinned lock text and fixed Dockerfile recipes.

These are input identity and consistency checks. The retained upstream documents and wheel
declarations do not authenticate their publisher, verify signatures or establish supply-chain
provenance. Matching a digest to the same recorded input is not independent evidence of image
contents. This input check does not inspect root filesystem layers or a completed image; the
separate host archive comparison below has a deliberately narrower, explicit observation scope.

The future recipe expects a minimal prepared context with only the selected `requirements.txt`,
`wheels/` and fixed `assets/`, rather than the repository checkout, user files or a live workspace.
T/A describe a wheel-only install with network disabled, `--no-index`, `--no-deps` and
`--require-hashes`. B describes no package install. Dockerfile instructions are inert text during
the check; their flags are not observed build isolation or runtime enforcement. The context helper
below materializes these inputs, while reviewed build/provisioning and verification of resulting
local image IDs remain separate operational work.

## Check from a development checkout

With the source development environment installed, run:

```bash
python -m scripts.generated_image_inputs --check
```

The default action is the same offline check. It reads local candidate inputs and prints a JSON
summary; it does not download wheels, contact a registry/Engine, execute Dockerfiles or import wheel
code. A successful summary still describes unbuilt candidates and grants no execution authority.

The optional Python API `verify_wheelhouse(root, wheelhouse, role, platform)` accepts an explicitly
supplied existing wheel directory. It checks the exact selected filenames, bounded ordinary-file
bytes, sizes/digests and inert wheel ZIP metadata. It neither downloads nor installs/imports those
wheels. Its additional byte observations still do not establish signatures, image contents, a
bit-reproducible build, effective resource limits or a verified repair.

## Fresh private build context

[scripts/generated_image_context.py](../../scripts/generated_image_context.py) provides
`prepare_image_context(repo, wheelhouse, parent, role, platform)`. It first rechecks the input
manifest and exact existing wheel set, then writes a fresh private bundle under the caller's
existing private, owned parent. The parent must be separate from the source repository and
wheelhouse. Output creation requires supported POSIX Python source; Windows writes are unsupported.
Both declared platforms can be prepared as inert inputs; this is not cross-platform build acceptance.

The build context contains only `Dockerfile`, `requirements.txt`, `wheels/` and the role's fixed
`assets/`. B retains its empty-wheel lock comment. It contains no application, generated test,
oracle, workspace record, account data or repository checkout. Context directories are `0700` and
ordinary single-link files are `0600`; opaque wheel bytes are copied without importing code or
unpacking payloads onto host directories.

The immutable `PreparedImageContext` result locates an external `receipt.json`, **outside** the build
context. Its inventory records relative names, sizes, hashes, file identities and manifest/recipe/
lock bindings without source paths. `check_prepared_context(context_path, receipt)` rechecks the
exact tree, bytes, modes, identities and external record before a future operational caller uses it.
Extra files, changed links/permissions or mismatched records refuse. A receipt is historical data,
not build authority, publisher authentication or proof against a hostile concurrent local writer.

Preparation never reuses a collision, retries a failed allocation or deletes partial output. Failures
retain the attempted/confirmed bundle and partial inventory, keeping allocation or descriptor-close
uncertainty explicit. Build, runtime and readiness flags remain false. There is no Docker invocation
or new public CLI in this helper.

## Host archive inventory and selected contents comparison

[scripts/generated_image_contents.py](../../scripts/generated_image_contents.py) operates on
explicitly supplied local, uncompressed rootfs tar files. `inventory_archive(path)` streams bounded
chunks into an immutable `ArchiveCatalog`: paths, types, modes, owners, sizes, file hashes and
bounded distribution metadata. It never extracts entries, resolves links on the host, imports code,
contacts an Engine or exports a container. Catalogs remain supplied observations, not authenticated
image identities or execution capabilities.

`compare_image_contents(repo, base_catalog, role_catalog, wheelhouse, role, platform)` currently
supports `linux/arm64` T/A/B comparisons only. It reuses the input/wheel checks, compares the supplied
base inventory, maintained guest assets, ordinary wheel payloads and installed distribution metadata,
and refuses missing/colliding/unexpected additions. This is a host-portable data comparison, not
Windows or additional-platform runtime support. The Docker-managed `etc/hostname`, `etc/hosts` and
`etc/resolv.conf` files must match the supplied base bytes and metadata, like every other baseline
entry. They are listed as compared files and are not excluded from the comparison.

Success reports granular facts such as `baseline_unchanged`, `wheel_payloads_verified`,
`maintained_assets_verified` and `installed_package_metadata_verified`. Pip-generated `RECORD` and
entrypoint scripts retain their paths/hashes in `unverified_generated_files`: their contents are
**not independently validated**. A supplied base catalog does not prove that an export came from
the declared base image. Timestamps, extended attributes, signatures, image configuration and
effective runtime behavior are not attested. Consequently `contents_verified`,
`image_configuration_verified`, `runtime_ready`, `runtime_invoked` and `execution_authorized` remain
false even when the selected comparison succeeds.

## Separate Engine bootstrap and remaining gates

The private [Engine metadata bootstrap](GENERATED_REPAIR_PREFLIGHT.md) can represent version/info
observations without inventing image IDs or an expected daemon identity. It uses only `/version`
and fixed `/v1.51/info`, and refuses an unsupported advertised API range before the second request.
Its engine identity is observed but unpinned; it does not create a full runtime profile, inspect
images or enable the executor. It is not a public CLI workflow.

Before generated execution, we still need reviewed image provisioning/contents and local image IDs,
effective stopped-container checks, current input/session decisions, bounded execution/capture and
confirmed exact guest cleanup, followed by installed before/after/restore acceptance and the local
results UI. `ready`, execution authority and verified repair remain unestablished. This document
does not accept #89 risk, close #152, change a version or authorize a release.
