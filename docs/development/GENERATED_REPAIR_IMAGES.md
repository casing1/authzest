<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/development/GENERATED_REPAIR_IMAGES.md">한국어</a>
</p>

# Generated repair images — pinned inputs, not built images

[Documentation index](../README.md) · [Guest entries](GENERATED_REPAIR_GUESTS.md) ·
[Runtime metadata](GENERATED_REPAIR_PREFLIGHT.md)

## Scope — 2026-11-15 KST

This partial [#152](https://github.com/casing1/authzest/issues/152) foundation records candidate
image inputs for the separate T/test, A/application and B/relay roles. It adds an offline input
checker, not an image builder, installer or enabled generated-code executor. #152 remains open.
The manifest keeps `status: "candidate-not-built"`, `image_ids: null` and
`contents_verified: false`; input consistency cannot manufacture ready images or a live profile.

No build, pull, load, base-layer retrieval, container creation/start, generated-code execution or AI
call is part of this change. There is no new public AuthZest command, runtime decision or release.

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
contents. No root filesystem layers or completed image are inspected.

The future recipe expects a minimal prepared context with only the selected `requirements.txt`,
`wheels/` and fixed `assets/`, rather than the repository checkout, user files or a live workspace.
T/A describe a wheel-only install with network disabled, `--no-index`, `--no-deps` and
`--require-hashes`. B describes no package install. Dockerfile instructions are inert text during
the check; their flags are not observed build isolation or runtime enforcement. Context preparation,
reviewed build/provisioning and verification of the resulting local image IDs remain separate work.

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
