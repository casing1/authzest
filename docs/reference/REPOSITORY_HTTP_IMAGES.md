<p align="center">
  <strong>English</strong> ·
  <a href="../i18n/ko/reference/REPOSITORY_HTTP_IMAGES.md">한국어</a>
</p>

# HTTP-only A/B image preparation

[Documentation index](../README.md) · [Frozen scope](../development/0.1.0-SCOPE.md) ·
[HTTP verification](REPOSITORY_HTTP_VERIFICATION.md) ·
[#210](https://github.com/casing1/authzest/issues/210)

## Delivered boundary

These development-source helpers check maintained image inputs, prepare a minimal private context
and compare supplied inert rootfs exports. They support only roles **A/B** and **linux/arm64**.
They do not download/install wheels, build images, contact an Engine, execute guest/target code or
apply a project patch. The external `repo-suggest --http-poc` CLI remains proposal-only.

The helpers use separate schema 2.0 `repository-http-*` reports and context objects. Existing
generated-repair image validators retain their closed contracts. Shared bounded file, wheel and
archive primitives do not make their old receipts valid HTTP execution authority.

## Pinned inputs and existing wheels

`scripts.repository_http_image_inputs` exposes `load_image_inputs`, `selected_inputs`,
`check_image_inputs` and `verify_wheelhouse`. The HTTP manifest binds the exact referenced dependency
manifest, base metadata, role-specific dependency closure/lock, maintained source assets, Dockerfile
bytes and canonical recipe hashes. Source paths and the HTTP guest root are closed, not supplied
commands or arbitrary repository files.

Wheel verification reads an already populated, exact selected wheelhouse. It checks bounded ZIP
structure, byte hashes, metadata, dependency declarations and compatible wheel tags without importing
wheel code. Extra/missing files, changed bytes, unsupported links and malformed metadata are refused.
The referenced dependency data is reused; no target dependency resolver or network installer is added.

From a development source checkout:

```bash
python -m scripts.repository_http_image_inputs
```

This observes maintained inputs only. It cannot establish an upstream signature, image identity,
effective runtime configuration, reproducible build or accepted executable image. The committed
image manifest stays `declared-not-built`, with null image IDs and readiness/content flags false.

## Minimal retained private contexts

`scripts.repository_http_image_context.prepare_image_context` accepts a repository root, an existing
wheelhouse, an existing private output parent, role and platform. The separate
`check_prepared_context` rechecks the prepared output and external receipt.

The context contains exactly `Dockerfile`, `requirements.txt`, `assets/` and `wheels/`. It excludes
target source, policy, independent cases/answers, account data, build receipts and the repository
checkout. The receipt lives beside the context. New directories use mode 0700 and copied ordinary
files use 0600; exclusive writes, descriptor identities, exact readback and membership checks refuse
overlap, aliases, changed inputs and extra output entries.

Each attempt allocates a fresh bundle. Failure retains partial output and distinguishes allocation,
ownership and descriptor-cleanup uncertainty; it does not silently reuse or delete a previous bundle.
Supported context writes require POSIX source Python. A trusted operator must exclude concurrent
same-user writers: synchronous filesystem operations do not provide an atomic transaction or a
whole-filesystem wall-clock bound.

Context receipts are historical observations, even when reconstructed as the public Python type.
Checking their files is not proof of a current trusted manifest or permission to build/run. A later
build operator must independently bind the current maintained inputs and actual selected context
bytes to its concrete decision. Every preparation report remains not-built/not-ready and grants no
execution or patch authority.

## Inert content comparison

`scripts.repository_http_image_contents` reuses bounded `inventory_archive` observations and exposes
a distinct `compare_image_contents`. It never extracts TAR/ZIP data or resolves archive links on the
host. Catalogs are caller-supplied observations, not authenticated image identities.

The comparison preserves every baseline entry, including Docker-managed host/resolver files, and
allows only the exact selected additions:

- Maintained files under `/opt/authzest-repository-http-guest` with the expected ownership and modes.
- A's `/input/project` directory or B's `/input` directory layout; no embedded target or test file.
- The selected locked wheel payloads and installed package metadata, with no extra packages.

Missing/extra entries, baseline changes, wrong bytes/type/mode/ownership, unexpected links and
collisions are refused. Pip-generated RECORD/entrypoint contents remain separately observed and
unverified; timestamps, xattrs, signatures and effective runtime behavior are not attested.

A successful comparison reports the bounded data checks, with `contents_verified=false`, image
configuration/readiness/execution flags false, authorization unknown and `verified_fix=false`.
An imported report cannot replace current direct host/Engine facts.

## Next connection

Concrete image build/inspection and actual image acceptance remain pending. Fresh HTTP-only file
checkpoints and sealed A inputs, Engine/stopped-container checks, direct before/after phases and the
copy/diff/apply/restore CLI operator are subsequent work. Final original-file approval, backup,
concurrent-edit refusal and recovery remain required under #152/#150. These offline helpers do not
close actual generation, installed full-flow acceptance, the saved-result viewer or release gates.
